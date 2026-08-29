import yaml
from Link import LinkBuilder, mux_setup
import Boards
import sys

if __name__ == "__main__":
    from optparse import OptionParser
    parser = OptionParser()

    parser.add_option("-f", "--configFile",default="../hexactrl-script/configs/initLD.yaml",
                      action="store", dest="configFile",
                      help="initial configuration yaml file")

    parser.add_option("-r", "--readConfig",
                      action="store_true", dest="readConfig",
                      help="print out the ROCs configuration")

    # Optional argument, False by default i.e. single-module setup by default
    parser.add_option("-m", "--mux",
                      action="store_true", dest="mux", default=False,
                      help="enable multi-module testing through the multiplexer board")
    # Optional argument, ignored by default (see above)
    parser.add_option("-s", "--slot",
                      action="store", dest="slot",
                      default="A", choices=["A", "B", "C"], metavar="{A,B,C}",
                      help="multiplexer board slot when --mux is set (A by default)")

    (options, args) = parser.parse_args()
    print(options)

    if options.mux:
        mux_setup(slot = options.slot)

    linkbuilder = LinkBuilder(slot = options.slot if options.mux else None)
    links = linkbuilder.links
    if len(links) == 1: board = Boards.CharBoard(links, multimodule=options.mux)
    if len(links) >= 2: board = Boards.HexaBoard(links, multimodule=options.mux)

    try:
        with open(options.configFile) as fin:
            config = yaml.safe_load(fin)
    except FileNotFoundError:
        print("%s not found"%(options.configFile))
        sys.exit(1)

    ans = board.configure(config)
    if options.readConfig:
        print( yaml.dump(board.read()) )
