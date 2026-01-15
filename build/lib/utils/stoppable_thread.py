"""スレッドを停止できるようにするためのクラスを定義するモジュール."""

import ctypes
import threading


class StoppableThread(threading.Thread):
    """スレッドを停止できるようにするためのクラス."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """スレッドを停止できるようにするためのクラス."""
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """スレッドを停止するためのメソッド."""
        if not self.is_alive():
            return

        # スレッドIDを取得して強制終了
        thread_id = self.ident
        if thread_id is not None:
            # 例外を発生させてスレッドを終了させる
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(thread_id),
                ctypes.py_object(SystemExit),
            )
            if res > 1:
                # 複数のスレッドに例外が送られた場合はリセット
                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    ctypes.c_long(thread_id),
                    ctypes.c_long(0),
                )

        self._stop_event.set()

    def stopped(self) -> bool:
        """スレッドが停止要求を受けたかどうかを確認するメソッド."""
        return self._stop_event.is_set()
