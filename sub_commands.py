import argparse
parser = argparse.ArgumentParser()
parser.add_argument("command", choices=['A','B','C'], help='this is help')
subparsers = parser.add_subparsers(help="sub command")

parser_a = subparsers.add_parser('a', help='a help')
parser_a.add_argument('bar', help='bar help')

parser_b = subparsers.add_parser('b', help='b help')
parser_b.add_argument('--baz', choices='XYZ',help='baz help')

args = parser.parse_args()
print(args)