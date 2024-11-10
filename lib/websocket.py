import base64
import re
import socket
from hashlib import sha1
from typing import Optional

from loguru import logger


class WebSocketClientUnit:
    def __init__(self, socket: socket.socket):
        self.__socket = socket

    def handshake(self) -> bool:
        ret = False
        try:
            handshake_req = self.__socket.recv(8192).decode()
            if (
                re.match(pattern="^GET", string=handshake_req, flags=re.IGNORECASE)
                is not None
            ):
                logger.info("======== Handshake from websocket client ========")
                logger.info(handshake_req)

                # 1. Obtain the value of the "Sec-WebSocket-Key" request header without any leading or trailing whitespace
                # 2. Concatenate it with "258EAFA5-E914-47DA-95CA-C5AB0DC85B11" (a special GUID specified by RFC 6455)
                # 3. Compute SHA-1 and Base64 hash of the new value
                # 4. Write the hash back as the value of "Sec-WebSocket-Accept" response header in an HTTP response
                swk = re.findall(
                    pattern="Sec-WebSocket-Key: (.*)", string=handshake_req
                )[0].strip()
                swka = swk + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
                swka_sha1_b64 = base64.b64encode(sha1(swka.encode()).digest()).decode()

                # HTTP/1.1 defines the sequence CR LF as the end-of-line marker
                handshake_resp = (
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    + "Connection: Upgrade\r\n"
                    + "Upgrade: websocket\r\n"
                    + f"Sec-WebSocket-Accept: {swka_sha1_b64}\r\n"
                    + "\r\n"
                )
                self.__socket.sendall(handshake_resp.encode())
                ret = True
            else:
                logger.error("handshake failed")
        except Exception as ex:
            logger.exception(ex)
        return ret

    def __get_header(self, final_frame: bool, cont_frame: bool) -> int:
        header = 1 if final_frame else 0  # fin: 0 = more frames, 1 = final frame
        header = (header << 1) + 0  # rsv1
        header = (header << 1) + 0  # rsv2
        header = (header << 1) + 0  # rsv3
        header = (header << 4) + (
            0 if cont_frame else 1
        )  # opcode : 0 = continuation frame, 1 = text
        header = (header << 1) + 0  # mask: server -> client = no mask
        return header

    def send(self, msg: str) -> bool:
        ret = False
        try:
            msg_buff = msg.encode()
            msg_len = len(msg_buff)
            for i in range(0, msg_len, 125):
                block_size = min(125, msg_len - i)
                header = self.__get_header(
                    final_frame=i + 125 >= msg_len, cont_frame=i != 0
                )
                header = (header << 7) + block_size
                self.__socket.sendall(header.to_bytes(2, "big"))
                self.__socket.sendall(msg_buff[i : i + block_size])
                ret = True
        except Exception as ex:
            logger.exception(ex)
        return ret

    # Frame format:
    #       0                   1                   2                   3
    #       0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    #      +-+-+-+-+-------+-+-------------+-------------------------------+
    #      |F|R|R|R| opcode|M| Payload len |    Extended payload length    |
    #      |I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
    #      |N|V|V|V|       |S|             |   (if payload len==126/127)   |
    #      | |1|2|3|       |K|             |                               |
    #      +-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
    #      |     Extended payload length continued, if payload len == 127  |
    #      + - - - - - - - - - - - - - - - +-------------------------------+
    #      |                               |Masking-key, if MASK set to 1  |
    #      +-------------------------------+-------------------------------+
    #      | Masking-key (continued)       |          Payload Data         |
    #      +-------------------------------- - - - - - - - - - - - - - - - +
    #      :                     Payload Data continued ...                :
    #      + - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
    #      |                     Payload Data continued ...                |
    #      +---------------------------------------------------------------+
    def recv(self) -> Optional[str]:
        ret = None
        try:
            resp_buff = b""
            while True:
                buff = self.__socket.recv(1 << 20)

                fin = (buff[0] & 0b10000000) != 0  # final frame
                _opcode = buff[0] & 0b00001111  # expecting 1 - text message
                mask = (
                    (buff[1] & 0b10000000) != 0
                )  # must be true, "All messages from the client to the server have this bit set"

                msglen = buff[1] & 0b01111111
                offset = 2

                if msglen == 126:
                    msglen = int.from_bytes(buff[2:4], "big")
                    offset = 4
                elif msglen == 127:
                    msglen = int.from_bytes(buff[2:10], "big")
                    offset = 10

                if msglen == 0:
                    logger.info("msglen = 0")
                elif mask:
                    masks = [
                        buff[offset],
                        buff[offset + 1],
                        buff[offset + 2],
                        buff[offset + 3],
                    ]
                    offset += 4

                    decoded = b""
                    for i in range(msglen):
                        if offset + i == len(buff):
                            buff = self.__socket.recv(min(8192, msglen - i))
                            offset = -i
                        decoded += bytes([buff[offset + i] ^ masks[i % 4]])

                    resp_buff += decoded

                    if fin:
                        break
            ret = resp_buff.decode()
        except Exception as ex:
            logger.exception(ex)
        return ret

    def close(self):
        self.__socket.close()


class WebSocketServer:
    def __init__(self, host: str, port: int):
        self.__host = host
        self.__port = port
        self.__server_socket = None

    def start(self):
        self.__server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__server_socket.bind((self.__host, self.__port))
        self.__server_socket.listen(5)

    def accept(self) -> Optional[WebSocketClientUnit]:
        ret = None
        try:
            if self.__server_socket is not None:
                client_socket, _ = self.__server_socket.accept()
                client_unit = WebSocketClientUnit(socket=client_socket)
                if client_unit.handshake():
                    ret = client_unit
            else:
                logger.error("socket is none")
        except Exception as ex:
            logger.exception(ex)
        return ret

    def close(self):
        if self.__server_socket is not None:
            self.__server_socket.close()
            self.__server_socket = None
        self.__host = None
        self.__port = None
