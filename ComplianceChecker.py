import pandas as pd 
import timing
import argparse
import os
from datetime import date
from datetime import datetime
from MergedExtractTool import Board
from MergedExtractTool import EntryBase
from MergedExtractTool import CalEntry
from MergedExtractTool import DiagEntry

parser = argparse.ArgumentParser()
parser.add_argument('-n','--name', help='Employee Name', required=True)
parser.add_argument('-i','--id', help='Employee ID', required=True)

def main():
    args = parser.parse_args()
    ti_name = args.name
    ti_id = args.id

    queue = get_jobs('./output')
    print(f'Found {len(queue)} new summary files to read in ./output .')

    # Loop through jobs in queue
    for job in queue:
        board_list, tester = load_profiles(job)

        # Note: might need to edit these for different tester configuration
        board_names = ['APU12', 'Digital Integration', 'DPU16', 'Master Clock', 'QMS', 'QTMU', 'SPU112']
        compliance_pass = 0
        compliance_total = 0

        # Get date today
        today = date.today().strftime('%m%d%Y')
        filename = f'{tester}_Compliance_Cert_{today}'

        with open(f'./output/{filename}.txt', 'w') as f:
            fail_boards = []
            """ print('---------------------------------------')
            print(f'{board_list[0].tester} Compliance Certificate') """

            f.write('---------------------------------------\n')
            f.write(f'{board_list[0].tester} Compliance Certificate\n')

            for board in board_list:
                if board.name in board_names:
                    compliance_total += 1
                    base_date = pd.to_datetime('1/1/10 0:0:0', infer_datetime_format=True)
                    cal_latest = None
                    check_latest = None
                    reason = ''

                    # Get latest cal and check entry
                    for cal_entry in board.cal_history:
                        entry_date = pd.to_datetime(f'{cal_entry.date} {cal_entry.time}', infer_datetime_format=True)
                        if entry_date > base_date:
                            if cal_entry.mode == 'Cal':
                                cal_latest = cal_entry
                            elif cal_entry.mode == 'Check':
                                check_latest = cal_entry

                            base_date = entry_date

                    # Get latest diag entry
                    base_date = pd.to_datetime('1/1/10 0:0:0', infer_datetime_format=True)
                    diag_latest = None
                    for diag_entry in board.diag_history:
                        entry_date = pd.to_datetime(f'{diag_entry.date} {diag_entry.time}', infer_datetime_format=True)
                        if entry_date > base_date:
                            diag_latest = diag_entry
                            base_date = entry_date

                    # Default compliance result is FAIL for now
                    compliance_result = 'FAIL'

                    if cal_latest and diag_latest and check_latest:
                        f.write('\n')
                        #print()
                        if check_latest.result == 'PASS' and cal_latest.result == 'PASS' and (diag_latest.result == 'PASS' or diag_latest.remark.strip() == '44V'):
                            if (cal_latest.sn == check_latest.sn and cal_latest.sn == diag_latest.sn) or board.name == 'Digital Integration':
                                # Set base dates for comparison (3 months for diag, 6 months for cal and check)
                                diag_base = monthdelta(datetime.today(), -3)
                                cal_base = monthdelta(datetime.today(), -6)

                                diag_latest_date = pd.to_datetime(f'{diag_entry.date} {diag_entry.time}', infer_datetime_format=True)
                                cal_latest_date = pd.to_datetime(f'{cal_latest.date} {cal_latest.time}', infer_datetime_format=True)
                                check_latest_date = pd.to_datetime(f'{check_latest.date} {check_latest.time}', infer_datetime_format=True)

                                if not diag_latest_date >= diag_base:
                                    reason += ' - Diag date is not within last 3 months' 
                                if not cal_latest_date >= cal_base:
                                    reason += ' - Cal date is not within last 6 months' 
                                if not check_latest_date >= cal_base:
                                    reason += ' - Check date is not within last 6 months' 
                                
                                if reason == '':
                                    if board.name == 'QMS':
                                        if cal_latest.dut_pn == 'ASM4731':
                                            compliance_result = 'PASS'
                                            compliance_pass += 1
                                    else:
                                        compliance_result = 'PASS'
                                        compliance_pass += 1
                            else:
                                reason = ' - Board SN Mismatch'
                        else:
                            # Append why board failed compliance
                            reason = ' - Fail in'
                            if cal_latest.result != 'PASS': reason += ' Cal' 
                            if check_latest.result != 'PASS': reason += ' Check' 
                            if not (diag_latest.result == 'PASS' or diag_latest.remark.strip() == '44V'): reason += ' Diag'
                            
                        # Write results to file
                        sn = None
                        check_date = pd.to_datetime(f'{check_latest.date} {check_latest.time}', infer_datetime_format=True)
                        diag_date = pd.to_datetime(f'{diag_latest.date} {diag_latest.time}', infer_datetime_format=True)

                        if check_date >= diag_date: sn = check_latest.sn
                        else: sn = diag_latest.sn

                        f.write(f'Slot {board.slot}: {board.name} SN {sn} - Result: {compliance_result}{reason}\n')
                        if board.name == 'QMS':
                            if cal_latest.dut_pn == 'ASM4731':
                                f.write('Calibrated with ASM4731: PASS\n')
                            else:
                                f.write(f'Calibrated with {cal_latest.dut_pn}: FAIL\n')
                        f.write(f'Last Calibration Date: {cal_latest.date} {cal_latest.time} - SN {cal_latest.sn} - Result: {cal_latest.result}\n')
                        f.write(f'Last Check Date: {check_latest.date} {check_latest.time} - SN {check_latest.sn} - Result: {check_latest.result}\n')
                        f.write(f'Last Diagnostics Date: {diag_latest.date} {diag_latest.time} - SN {diag_latest.sn} - Result: {diag_latest.result}\n')

                        if diag_latest.remark:
                            #print(f'Diagnostics failure: {diag_latest.remark}')
                            f.write(f'Diagnostics failure: {diag_latest.remark}\n')

                        if compliance_result == 'FAIL':
                            fail_boards.append(f'{board.name} - {board.slot}')
                    else:
                        # Unlikely to happen, but capture just in case
                        f.write(f'Slot {board.slot}: {board.name} -')
                        if not cal_latest:
                            f.write(f' No CAL record')
                        if not check_latest:
                            f.write(f' No CHECK record')
                        if not diag_latest:
                            f.write(f' No DIAG record')
                        f.write('\n')

            # Calculate compliance score and append user identity
            score = round(compliance_pass/compliance_total*100, 1)

            print(f'\n{tester} RESULT: {score}% COMPLIANT ({compliance_pass} out of {compliance_total} compliant)')
            date_today = datetime.today().strftime('%m/%d/%Y %H:%M:%S')
            print(f'RUN BY: {ti_id} {ti_name} on {date_today}')

            f.write(f'\nRESULT: {score}% COMPLIANT ({compliance_pass} out of {compliance_total} compliant) \n')
            if score == 100:
                f.write('DECISION: Tester may be released for production.\n')
            else:
                f.write('DECISION: Please resolve failures for')
                for fail in fail_boards:
                    if fail == fail_boards[-1]:
                        f.write(f' {fail}')
                    else:
                        f.write(f' {fail},')
                f.write(' before running compliance checker again.\n')

            f.write(f'RUN BY: {ti_id} {ti_name} on {date_today}')

        print(f'{compliance_pass}/{compliance_total}')


def load_profiles(filepath):
    board_list = []
    tester_num = None
    with open(filepath, 'r') as f:
        line = f.readline()
        line = f.readline()
        while line:
            string = line.split(',')
            tester = string[0].strip()
            name = string[1].strip()
            slot = string[2].strip()
            dib_sn = string[3].strip()
            dib_pn = string[4].strip()
            self_test = string[5].strip()
            date = string[6].strip()
            time = string[7].strip()
            mode = string[8].strip()
            sn = string[9].strip()
            rev = string[10].strip()
            result = string[11].strip()
            remark = string[12].strip()

            current_board = None
            if board_list:
                for board in board_list:
                    if board.name == name and (board.slot in slot or slot in board.slot):
                        current_board = board
                        break
            
            if not current_board:
                current_board = Board(name, slot, tester)
                board_list.append(current_board)
            
            if mode in ('Cal', 'Check'):
                current_board.cal_history.append(CalEntry(dib_sn, date, time, sn, result, remark, '', mode, rev, self_test, dib_pn))
            elif mode == 'Diag':
                current_board.diag_history.append(DiagEntry(dib_pn, date, time, sn, result, remark, '', name, slot))
            
            line = f.readline()
            tester_num = tester

    return board_list, tester_num

def get_jobs(filepath):
    '''
    Returns a list of log file paths (STR) to be processed next.
    '''
    files_actual = []

    """ for child in Path(filepath).iterdir():
        if child.is_file():
            files_actual.append(str(child)) """

    for root, dirs, files in os.walk(filepath):
        for file in files:
            #append the file name to the list
            if(file.endswith(".csv")):
                files_actual.append(os.path.join(root,file))
    
    return files_actual

def monthdelta(date, delta):
    # Offsets the input date's month with delta
    m, y = (date.month+delta) % 12, date.year + ((date.month)+delta-1) // 12
    if not m: m = 12
    d = min(date.day, [31,
        29 if y%4==0 and not y%400==0 else 28,31,30,31,30,31,31,30,31,30,31][m-1])
    return date.replace(day=d,month=m, year=y)

if __name__ == '__main__':
    main()