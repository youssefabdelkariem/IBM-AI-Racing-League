"""Entry point: the official starter loop of snakeoil3_gym.py (Client(p=3001); get_servers_input / drive / respond_to_server) with our
driver in place of drive_example. snakeoil3_gym.py in this folder is the unmodified starter file.

Usage (TORCS must be waiting in a Quick Race with scr_server 1; see README_WINDOWS.md):
    python run_controller.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import snakeoil3_gym as snakeoil3
import submission_driver


def main():
    C = snakeoil3.Client(p=3001)
    submission_driver.protect_gc()          # after the handshake, before the race moves
    for step in range(C.maxSteps, 0, -1):
        C.get_servers_input()
        submission_driver.drive(C)
        C.respond_to_server()
        if C.so is None:                    # the server has ended the race (client already shut down): stop looping on stale data
            break
    C.shutdown()


if __name__ == '__main__':
    main()

