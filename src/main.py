import uasyncio
from enviro_pi import EnviroPi

def main():
    enviro_pi = EnviroPi()
    uasyncio.run(enviro_pi.run())

if __name__ == "__main__":
    main()