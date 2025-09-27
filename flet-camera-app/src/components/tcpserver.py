import socket
import threading
import queue
import time

def start_tcp_server(host: str, port: int, message_queue: queue.Queue):
    """
    สร้างและเริ่ม TCP server (รองรับ stop แบบ graceful)
    คืนค่า control object ที่มี:
        .thread        => server thread
        .stop()        => เรียกเพื่อหยุด server
        .is_running()  => ตรวจสอบสถานะ
    """
    stop_event = threading.Event()
    client_threads = []

    def handle_client(conn, addr):
        print(f"[SERVER] Client เชื่อมต่อเข้ามาจาก: {addr}")
        with conn:
            conn.settimeout(2.0)
            while not stop_event.is_set():
                try:
                    data = conn.recv(1024)
                    if not data:
                        break
                    message = data.decode('utf-8', errors='replace')
                    message_queue.put(message)
                    response = f"Server received: {message}"
                    conn.sendall(response.encode('utf-8'))
                except socket.timeout:
                    continue
                except (ConnectionResetError, OSError):
                    break
        print(f"[SERVER] Client {addr} ตัดการเชื่อมต่อแล้ว")

    def server_worker():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((host, port))
                s.listen()
                s.settimeout(1.0)  # เพื่อตรวจ stop_event
                print(f"[SERVER] กำลังรอรับการเชื่อมต่อที่ {host}:{port}")
                while not stop_event.is_set():
                    try:
                        conn, addr = s.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
                    client_threads.append(t)
                    t.start()
        finally:
            print("[SERVER] server_worker ออกจาก loop แล้ว (กำลังปิด)")

    server_thread = threading.Thread(target=server_worker, daemon=True)
    server_thread.start()

    class TCPServerControl:
        def stop(self, timeout: float = 3.0):
            if stop_event.is_set():
                return
            print("[SERVER] กำลังหยุด...")
            stop_event.set()
            # ปลุก accept() ถ้ายังบล็อก (เชื่อมต่อ dummy)
            try:
                with socket.create_connection((host, port), timeout=0.5):
                    pass
            except Exception:
                pass
            server_thread.join(timeout=timeout)
            for t in client_threads:
                t.join(timeout=0.5)
            print("[SERVER] หยุดเรียบร้อย")
        def is_running(self):
            return server_thread.is_alive() and not stop_event.is_set()
        @property
        def thread(self):
            return server_thread

    return TCPServerControl()

# --- ตัวอย่างการใช้งาน ---
if __name__ == "__main__":
    HOST = '127.0.0.1'
    PORT = 5001
    incoming_messages = queue.Queue()
    tcp_server = start_tcp_server(HOST, PORT, incoming_messages)

    print("[MAIN] ทำงานอื่นต่อไป... กด Ctrl+C เพื่อออก")
    try:
        while True:
            try:
                message = incoming_messages.get(timeout=0.2)
                print(f"[MAIN] ได้รับ: {message}")
            except queue.Empty:
                pass
            # งานอื่น...
    except KeyboardInterrupt:
        print("\n[MAIN] รับสัญญาณ KeyboardInterrupt -> ปิด server")
    finally:
        tcp_server.stop()
        print("[MAIN] จบโปรแกรมแล้ว")