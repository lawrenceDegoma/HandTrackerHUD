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
    
    # Wakeup word configuration
    wakeup_words = ["hey computer", "hey computer.", "a computer", "hey computer,"]
    is_awake = False
    awake_timeout = 5.0  # seconds to stay awake after wakeup word
    awake_start_time = None
    
    print("Voice control: Listening for 'Hey computer'...")
    
    while not stop_event.is_set():
        try:
            with mic as source:
                # Shorter timeout when waiting for wakeup word
                timeout = 2 if not is_awake else 4
                phrase_limit = 3 if not is_awake else 6
                audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
            
            try:
                text = r.recognize_google(audio).lower()
                
                if not is_awake:
                    # Check for wakeup word
                    if any(wakeup in text for wakeup in wakeup_words):
                        is_awake = True
                        awake_start_time = time.time()
                        print("Voice control: Awake! Listening for commands...")
                        # Check if there's a command in the same phrase after wakeup word
                        for wakeup in wakeup_words:
                            if wakeup in text:
                                # Extract text after wakeup word
                                remaining_text = text.split(wakeup, 1)[1].strip()
                                if remaining_text and len(remaining_text) > 2:
                                    print(f"Voice control: Command detected: '{remaining_text}'")
                                    cmd_queue.put(remaining_text)
                                break
                else:
                    # We're awake, process the command
                    print(f"Voice control: Command detected: '{text}'")
                    cmd_queue.put(text)
                    is_awake = False  # Go back to sleep after processing command
                    awake_start_time = None
                    print("Voice control: Going back to sleep. Say 'Hey computer' to wake up.")
                    
            except sr.UnknownValueError:
                # Check if we should timeout from being awake
                if is_awake and awake_start_time and time.time() - awake_start_time > awake_timeout:
                    is_awake = False
                    awake_start_time = None
                    print("Voice control: Timeout. Going back to sleep. Say 'Hey computer' to wake up.")
                continue
            except sr.RequestError as e:
                print("Voice control: request error:", e)
                time.sleep(1)
        except sr.WaitTimeoutError:
            # Check if we should timeout from being awake
            if is_awake and awake_start_time and time.time() - awake_start_time > awake_timeout:
                is_awake = False
                awake_start_time = None
                print("Voice control: Timeout. Going back to sleep. Say 'Hey computer' to wake up.")
            continue
        except Exception as e:
            print("Voice control error:", e)
            time.sleep(1)


def start_voice_listener(cmd_queue: queue.Queue):
    stop_event = threading.Event()
    t = threading.Thread(target=_listen_loop, args=(cmd_queue, stop_event), daemon=True)
    t.start()
    return stop_event
