import pandas as pd 
import timing
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-f','--file', help='Location path of the input .csv file from SummarizerTool.', required=True)
parser.add_argument('-s','--start', help='Starting date of Strike 3 check. Format: m/d/yyyy', required=True)
parser.add_argument('-e', '--end', help='End date of Strike 3 check. Format: m/d/yyyy', required=True)

def main():
    args = parser.parse_args()

    # Set ipython's max row display
    pd.set_option('display.max_row', None)

    # Set iPython's max column width to 50
    pd.set_option('display.max_columns', 100)

    date_start = pd.to_datetime(args.start, format='%m/%d/%Y')
    date_end = pd.to_datetime(args.end, format='%m/%d/%Y')

    #date_start = pd.to_datetime('1/1/2020', format='%m/%d/%Y')
    #date_end = pd.to_datetime('1/2/2020', format='%m/%d/%Y')

    # Read csv
    df = pd.read_csv(args.file, sep=',\t?', dtype={'DIB SN':str, 'SN':str, 'REV':str},engine='python', parse_dates=[6], infer_datetime_format=True) 
    
    df['Date2'] = df['Date'].dt.date

    # Select data that is in within given date_start and date_end
    df = df.loc[(df['Date2'] >= date_start.date()) & (df['Date2'] <= date_end.date())]

    # Convert Date to string
    df['Date'] = df['Date'].dt.strftime('%m/%d/%Y')
    
    # Pivot the table
    df = df.groupby(['Board', 'SN', 'Slot', 'Date', 'Time', 'Mode', 'Result']).size().unstack().fillna(0)

    if '????' in df.columns:
        df = df.drop(columns='????') #Hide ???? for now
    if 'PASS' in df.columns: #Safety check in case PASS doesnt exist
        df = df.drop(columns='PASS')
    if 'FAIL' in df.columns:#Safety check in case FAIL doesnt exist
        df = df.loc[df['FAIL'] > 0]

    if not df.empty:
        # Populate list of boards that has at least 1 failure
        data = {'Board':df.index.get_level_values(0).tolist(), 'SN':df.index.get_level_values(1).tolist()}
        board_sn = pd.DataFrame(data).drop_duplicates()
        board_sn = list(zip(board_sn['Board'], board_sn['SN']))
        strike3_list = [] #holds the strike3 objects

        for item in board_sn:
            strike3_list.append(Strike3((item[0],item[1])))
        
        # Store specific information of failures to respective board-sn objects
        curr_board = strike3_list[0]
        for row in df.index.values:
            if curr_board.board_sn != (row[0], row[1]):
                for board in strike3_list:
                    if board.board_sn == (row[0], row[1]): 
                        curr_board = board
                        break
            curr_board.fails.append(Fail(row[2],row[3],row[4],row[5]))

        #print(df)

        # List of strike 3 flagged boards for printing
        flagged = []
        for item in strike3_list:
            if len(item.fails) >= 3:
                flagged.append(item)
            print(item)

        print(f'STRIKE 3 ALERT: Action needed for the following boards:')
        for item in flagged:
            print(f'{item.board_sn[0]} - {item.board_sn[1]}')

        # Output excel sheet
        with pd.ExcelWriter('./output/strike3.xlsx', date_format='mmmm/dd/yyyy') as writer:  
            for board, sn in board_sn:
                temp_df = df.xs(board, level=0).xs(sn, level=0)
                temp_df.to_excel(writer, f'{board}_{sn}')
                #print(df.xs(board, level=0).xs(sn, level=0))
    else:
        print('RESULT: No failures for given date range.')

class Strike3(object):
    def __init__(self, board_sn):
        self.board_sn = board_sn
        self.fails = []
    
    def __str__(self):
        string1 = f'{self.board_sn[0]} - {self.board_sn[1]} | FAILURES: {len(self.fails)}\n'
        string2 = f'Last failure: {self.fails[-1].date} {self.fails[-1].time} on Slot {self.fails[-1].slot}\n'
        return string1+string2

    @classmethod
    def get_strike3(cls):
        return None, None

class Fail(object):
    def __init__(self, slot, date, time, mode):
        self.slot = slot
        self.date = date
        self.time = time
        self.mode = mode

if __name__ == '__main__':
    main()