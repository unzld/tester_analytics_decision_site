from pathlib import Path
from os import mkdir
from dataclasses import dataclass
from shutil import rmtree
import jsonpickle
import json
import re

rx_diag = {}
rx_cal = {}
rx_cal_res = {}

def main():
    global rx_tester_info
    global rx_cal
    global rx_cal_res
    global rx_diag

    rx_tester_info = load_regex_dict('config/rx_tester_info.csv')
    rx_cal = load_regex_dict('config/rx_cal.csv')
    rx_cal_res = load_regex_dict('config/rx_cal_res.csv')
    rx_diag = load_regex_dict('config/rx_diag.csv')

    filepath = 'C:/Users/a0489136/Desktop/Project/Main Project/samplelogs/clprea83/Cal_files'
    
    #Board.clear_all_profiles()
    #gen_profiles('C:/Users/a0489136/Desktop/Project/Main Project/samplelogs/clprea83/Diag_files/Diag_CLPREA83_02082020.log', 'CLPREA83')

    #Get list of logs to process
    queue = get_jobs(filepath)
    print(f'jobs to do: {len(queue)}')
    
    #Load profiles from ./profiles
    board_list = load_profiles()

    #Process each job in queue
    for job in queue:
        load_cal_result(job, board_list)

    #Save profile changes to disk
    save_profiles(board_list)

    #Add finished jobs to file_list.json
    update_filelist(queue)
    print('hey')

def load_cal_result(filepath, board_list):
    with open(filepath) as f:
        line = f.readline()
        loaded_tester_info = False
        dut = ''
        self_test = ''
        while line:
            #print(line)
            #Parse every line using parse_line and store it to key and match
            if loaded_tester_info:
                key, match = parse_line(line, rx_cal)
            else:
                key, match = parse_line(line, rx_tester_info)

            #If key is not empty, it means we got a match
            if key and loaded_tester_info:
                btype = match.group('btype').strip() #Board name
                slot = match.group('slot').strip() #Stores board slot

                mode = match.group('mode').strip() #Stores current test mode (Cal or Chk)
                sn = match.group('sn').strip() #Stores board SN
                rev = match.group('rev').strip()
                remark = ''

                #Some boards do not include slot number in the beginning (MCU and DIG INTEG)
                #For now, set it to -1
                if not(len(slot)):
                    slot = '00'
                
                #Get the correct board reference
                board = None #current board reference
                for item in board_list:
                    if item.name.lower() == btype.lower() and item.slot == slot:
                        board = item
                        break
                    
                    if item.name == 'Master Clock' and btype == 'MCU':
                        board = item
                        break
                    
                    if item.slot.isnumeric():
                        if item.name.lower() == btype.lower() and int(item.slot) == int(slot):
                            board = item
                            break

                #Check for results
                res_line = f.readline()
                while(res_line):
                    res_key, res_match = parse_line(res_line, rx_cal_res)

                    if res_key == 'cal' or  res_key == 'chk':
                        #Change UPDATED to PASS
                        if res_match.group('res').strip() == 'UPDATED': res = 'PASS'
                        else: res = res_match.group('res').strip()

                        date = res_match.group('date').strip()
                        time = res_match.group('time').strip()
                        board.cal_history.append(CalEntry(dut, date, time, sn, res, remark, mode, rev, self_test))
                        break
                    
                    res_line = f.readline()
            elif key and not loaded_tester_info:
                if key == 'self_test':
                    self_test = match.group('self_test')
                elif key == 'dut' and self_test == 'PASSED':
                    dut = match.group('dut_sn')
                    loaded_tester_info = True
            #Go to next line
            line = f.readline()
    print(f'Processed log from {filepath}.')

def gen_profiles(filepath, tester):
    '''
    Generates board profiles from a log file. Only has to be used once unless there are physical changes to the tester.
    
    Returns a list of Board objects.
    '''

    finished = False
    table_left = []
    table_right = []

    with open(filepath) as f:
        line = f.readline()
        while line:
            #print(line)
            #Parse every line using parse_line and store it to key and match
            key, match = parse_line(line, rx_diag)

            if key == 'diag_table_long':
                slot1 = match.group('slot')
                if not slot1:
                    slot1 = '00'
                board1 = Board(match.group('btype').strip(), slot1, tester)
                table_left.append(board1)

                slot2 = match.group('slot2')
                if not slot2:
                    slot2 = '00'
                board2 = Board(match.group('btype2').strip(), slot2, tester)
                table_right.append(board2)
            elif key == 'diag_table_end':
                finished = True
            
            if finished: break
            else: line = f.readline()

    board_list = table_left + table_right

    for item in board_list:
        if item.name == 'DPU':
            item.name = 'DPU16'
        item.generate_profile()

    return table_left + table_right

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

def save_profiles(board_list):
    '''
    Save profiles from board_list to JSON format located in ./profile.
    '''
    for board in board_list:
        board.generate_profile()

def get_jobs(filepath):
    '''
    Returns a list of log file paths (STR) to be processed next.
    '''
    files_actual = []
    files_json = []
    process_queue = []

    for child in Path(filepath).iterdir():
        if child.is_file():
            files_actual.append(str(child))

    #check if file_list.json exists
    if Path(f'./config/file_list.json').exists():
        #read json file
        with open('./config/file_list.json', 'r') as f:
            try:
                files_json = json.load(f)
            except json.decoder.JSONDecodeError:
                print('Reading file_list: The file_list.json is either empty or corrupted. Continuing..')
        
        for item in files_actual:
            if item not in files_json and item.lower().endswith('.log'):
                process_queue.append(item)
    else:
        process_queue = files_actual.copy()
    
    return process_queue

def update_filelist(done_jobs):
    '''
    Updates ./config/file_list.json to add processed logs
    '''
    #save to json
    files_json = []
    
    if Path(f'./config/file_list.json').exists(): mode = 'r+'
    else: mode = 'w'
    #read json file
    with open('./config/file_list.json', mode) as f:
        try:
            if mode == 'r+': files_json = json.load(f)
        except json.decoder.JSONDecodeError:
            print('Saving file_list: The file_list.json is either empty or corrupted. Continuing..')
        finally:
            for item in done_jobs:
                if item not in files_json and item.lower().endswith('.log'):
                    files_json.append(item)
            f.seek(0)
            json.dump(files_json, f, indent=4)
            
def parse_line(line, dict):
    #For each entry in the regex dictionary, check if it has a match with the input line
    for key, rx in dict.items():
        match = rx.search(line)
        if match:
            #If it matches, return key and match object
            return key, match
    
    #Else, return None
    return None, None

def load_regex_dict(filepath):
    dict = {}
    with open(filepath) as f:
        line = f.readline()
        while line:
            #Parse line and split into key and value then store into dictionary
            x = line.strip().strip('\n').split(',',1)
            dict[x[0]] = re.compile(x[1])
            line = f.readline()
    return dict

@dataclass
class Log:
    ''' Object for tracking individual files'''
    filename : str
    size : int

class Board(object):
    def __init__(self, name, slot, tester):
        '''
        Constructor for Board.

        Arguments:
        name -- board name
        slot -- board slot
        tester -- tester name
        '''
        self.name = name
        self.slot = slot
        self.tester = tester

        self.cal_history = []
        self.diag_history = []
        self.path = None
    
    def generate_profile(self):
        if not Path('./profiles').exists():
            try:
                mkdir('./profiles')
            except OSError:
                print('Failed creating profile directory.')
        slot = self.slot.replace('>', '', 1)
        if not self.path: self.path = f'./profiles/{self.name}_{slot}.json'
        with open(self.path, 'w') as f:
            board_json = jsonpickle.encode(self)
            f.write(board_json)
    
    def add_cal_entry(self, entry):
        self.cal_history.append(entry)

    def add_diag_entry(self, entry):
        self.diag_history.append(entry)
    
    def clear_cal_history(self):
        self.cal_history.clear()

    def clear_diag_history(self):
        self.diag_history.clear()
    
    @classmethod
    def clear_all_profiles(cls):
        if Path('./profiles').exists():
            try:
                rmtree('./profiles')
            except OSError:
                print('Failed deleting profile directory.')
           
class EntryBase(object):
    def __init__(self, dut, date, time, sn, result, remark):
        self.dut = dut
        self.date = date
        self.time = time
        self.sn = sn
        self.result = result
        self.remark = remark

class CalEntry(EntryBase):
    def __init__(self, dut, date, time, sn, result, remark, mode, rev, self_test):
        EntryBase.__init__(self, dut, date, time, sn, result, remark)
        self.mode = mode
        self.rev = rev
        self.self_test = self_test

class DiagEntry(EntryBase):
    pass

if __name__ == '__main__':
    main()