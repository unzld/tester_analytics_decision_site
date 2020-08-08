import argparse
from pathlib import Path
import jsonpickle
import os
from TesterMonitoringTool import Board
from TesterMonitoringTool import EntryBase
from TesterMonitoringTool import CalEntry
from TesterMonitoringTool import DiagEntry
from datetime import date
from os import mkdir

parser = argparse.ArgumentParser()

parser.add_argument('-m','--merge', action='store_true', help='Merge cal and diag entries in summary output.')
parser.add_argument('-f', '--file', help='Optional: summarizes the specified .LOG file instead.')

def main():
    args = parser.parse_args()
    board_list = []
    
    if args.file:
        board_list = load_profiles()
        gen_file(board_list, args.file)
    else:
        board_list = load_profiles()

        if args.merge:
            gen_csv_merged(board_list)
        else:
            gen_csv_cal(board_list)
            gen_csv_diag(board_list)

def load_profiles():
    '''
    Loads existing profiles in ./profiles and returns them as a list of Board objects
    '''
    board_list = []
    for profile in Path('./profiles').iterdir():
        if profile.is_file():
            #load profile
            with open(profile, 'r') as f:
                json_str = f.read()
                board = jsonpickle.decode(json_str)
                #print(f'{board.name} {board.slot} {board.tester}')
                board_list.append(board)
    
    print(f'{len(board_list)} board profiles loaded.')

    return board_list

def gen_csv_cal(board_list):
    today = date.today().strftime('%m%d%Y')
    filename = f'Summary_Cal_All_{today}'
    empty = True
    if not Path('./output').exists():
        try:
            mkdir('./output')
        except OSError:
            print('Failed creating output directory.')
            exit(2)

    with open(f'./output/{filename}.csv', 'w') as f:
        f.write(f'Tester,Board,Slot,DIB SN,DIB PN,Self-Test,Date,Time,Mode,SN,REV,Result,Remark\n')
        for board in board_list:
            for entry in board.cal_history:
                empty = False
                f.write(f'{board.tester},{board.name},\t{board.slot},\t{entry.dut},\t{entry.dut_pn},{entry.self_test},\t{entry.date},\t{entry.time},{entry.mode},\t{entry.sn},{entry.rev},{entry.result},{entry.remark}\n')
    
    if empty:
        os.remove(f'./output/{filename}.csv')
        print(f'Process finished. Calibration summary NOT generated. Run TesterMonitoringTool to update boards.')
    else:
        print(f'Process finished. Calibration summary located at ./output/{filename}.csv.')

def gen_csv_diag(board_list):
    today = date.today().strftime('%m%d%Y')
    filename = f'Summary_Diag_All_{today}'
    empty = True
    if not Path('./output').exists():
        try:
            mkdir('./output')
        except OSError:
            print('Failed creating output directory.')
            exit(2)

    with open(f'./output/{filename}.csv', 'w') as f:
        f.write(f'Tester,Board,Slot,DIB PN,Date,Time,SN,Result,Remark\n')
        for board in board_list:
            for entry in board.diag_history:
                empty = False
                if entry.result == 'P': entry.result = 'PASS'
                f.write(f'{board.tester},{board.name},\t{board.slot},{entry.dut},\t{entry.date},\t{entry.time},\t{entry.sn},{entry.result},{entry.remark}\n')
    
    if empty:
        os.remove(f'./output/{filename}.csv')
        print(f'Process finished. Diagnostic summary NOT generated. Run TesterMonitoringTool to update boards.')
    else:
        print(f'Process finished. Diagnostic summary located at ./output/{filename}.csv.')

def gen_csv_merged(board_list):
    today = date.today().strftime('%m%d%Y')
    filename = f'Summary_Cal_Diag_All_{today}'
    empty = True
    if not Path('./output').exists():
        try:
            mkdir('./output')
        except OSError:
            print('Failed creating output directory.')
            exit(2)

    with open(f'./output/{filename}.csv', 'w') as f:
        f.write(f'Tester,Board,Slot,DIB SN,DIB PN,Self-Test,Date,Time,Mode,SN,REV,Result,Remark\n')
        for board in board_list:
            for entry in board.cal_history + board.diag_history:
                if isinstance(entry, CalEntry):
                    empty = False
                    f.write(f'{board.tester},{board.name},\t{board.slot},\t{entry.dut},\t{entry.dut_pn},{entry.self_test},\t{entry.date},\t{entry.time},{entry.mode},\t{entry.sn},{entry.rev},{entry.result},{entry.remark}\n')
                elif isinstance(entry, DiagEntry):
                    empty = False
                    if entry.result == 'P': entry.result = 'PASS'
                    f.write(f'{board.tester},{board.name},\t{board.slot},N/A,\t{entry.dut},N/A,\t{entry.date},\t{entry.time},Diag,\t{entry.sn},N/A,{entry.result},{entry.remark}\n')
    
    if empty:
        os.remove(f'./output/{filename}.csv')
        print(f'Process finished. Summary NOT generated. Run TesterMonitoringTool to update boards.')
    else:
        print(f'Process finished. Merged summary located at ./output/{filename}.csv.')

def gen_file(board_list, filename):
    mode = ''

    if 'diag' in filename.lower():
        mode = 'diag'
    elif 'cal' in filename.lower():
        mode = 'cal'

    if not Path('./output').exists():
        try:
            mkdir('./output')
        except OSError:
            print('Failed creating output directory.')
            exit(2)

    empty = True
    
    if mode == 'cal':
        with open(f'./output/Summary_{filename}.csv', 'w') as f:
            f.write(f'Tester,Board,Slot,DUT SN,Self-Test,Date,Time,Mode,SN,REV,Result,Remark\n')
            for board in board_list:
                for entry in board.cal_history:
                    if entry.logname.lower().endswith(f'{filename.lower()}.log'):
                        empty = False
                        f.write(f'{board.tester},{board.name},{board.slot},\t{entry.dut},{entry.self_test},\t{entry.date},\t{entry.time},{entry.mode},\t{entry.sn},{entry.rev},{entry.result},{entry.remark}\n')

    elif mode == 'diag':
        with open(f'./output/Summary_{filename}.csv', 'w') as f:
            f.write(f'Tester,Board,Slot,DUT Board,Date,Time,SN,Result,Remark\n')
            for board in board_list:
                for entry in board.diag_history:
                    if entry.logname.lower().endswith(f'{filename.lower()}.log'):
                        empty = False
                        if entry.result == 'P': entry.result = 'PASS'
                        f.write(f'{board.tester},{board.name},\t{board.slot},{entry.dut},\t{entry.date},\t{entry.time},\t{entry.sn},{entry.result},{entry.remark}\n')

    if empty:
        print(f'Process finished. No entries associated with specified filename {filename}.')
        os.remove(f'./output/Summary_{filename}.csv')
    else:
        print(f'Process finished. Output located at ./output/Summary_{filename}.csv.')

if __name__ == '__main__':
    main()