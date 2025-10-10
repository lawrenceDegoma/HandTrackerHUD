import threading
import queue
import time
import speech_recognition as sr


def _listen_loop(cmd_queue: queue.Queue, stop_event: threading.Event):
    r = sr.Recognizer()
    try:
        mic = sr.Microphone()
    except Exception as e:
        print("Voice control: no microphone available or microphone init failed:", e)
        return

    with mic as source:
        r.adjust_for_ambient_noise(source, duration=0.5)
    while not stop_event.is_set():
        try:
            with mic as source:
                audio = r.listen(source, timeout=4, phrase_time_limit=6)
            try:
                text = r.recognize_google(audio).lower()
                cmd_queue.put(text)
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                print("Voice control: request error:", e)
                time.sleep(1)
        except sr.WaitTimeoutError:
            continue
        except Exception as e:
            print("Voice control error:", e)
            time.sleep(1)


def start_voice_listener(cmd_queue: queue.Queue):
    stop_event = threading.Event()
    t = threading.Thread(target=_listen_loop, args=(cmd_queue, stop_event), daemon=True)
    t.start()
    return stop_event
