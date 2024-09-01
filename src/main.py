import uasyncio
from picow_growmat import PicoWGrowmat

def main():
    growmat = PicoWGrowmat()
    uasyncio.run(growmat.run())

if __name__ == "__main__":
    main()