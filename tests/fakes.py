"""测试用虚拟串口：两个端点互连，模拟 pyserial 接口子集。"""
import queue


class FakeSerial:
    def __init__(self, rx_queue: queue.Queue, tx_queue: queue.Queue):
        self._rx = rx_queue
        self._tx = tx_queue
        self.is_open = True
        self.timeout = 1.0
        self.dtr = False
        self.rts = False
        self.write_timeout = 5.0

    def write(self, data: bytes) -> int:
        for b in data:
            self._tx.put(b)
        return len(data)

    def read(self, n: int = 1) -> bytes:
        try:
            first = self._rx.get(timeout=self.timeout)
        except queue.Empty:
            return b""
        out = bytearray([first])
        while len(out) < n:
            try:
                out.append(self._rx.get_nowait())
            except queue.Empty:
                break
        return bytes(out)

    @property
    def in_waiting(self) -> int:
        return self._rx.qsize()

    def reset_input_buffer(self) -> None:
        while True:
            try:
                self._rx.get_nowait()
            except queue.Empty:
                break

    def reset_output_buffer(self) -> None:
        pass

    def cancel_read(self) -> None:
        pass

    def close(self) -> None:
        self.is_open = False


def make_fake_serial_pair():
    a_rx: queue.Queue = queue.Queue()
    b_rx: queue.Queue = queue.Queue()
    a = FakeSerial(a_rx, b_rx)
    b = FakeSerial(b_rx, a_rx)
    return a, b
