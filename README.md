# Tester Analytics Decision Site
This is a project for TI Virtual Internship 2020, which focuses mainly on extracting data related to tester boards to generate automated statistical and analytical reports.
## TesterMonitoringTool
Monitors a given directory for new logs, generates (on first run) and updates board profiles when a new log is detected.\
Board profiles are located in './profiles'.
## SummarizerTool
Extracts data from the board profiles and summarizes them in .csv format. By default, summarizes the latest logs from TesterMonitoringTool.\
Output folder is in './output'.

### Commandline parameters:
-f PATH, --file PATH: Optional. Summarizes the single log in the specified path instead.\
-m, --merge : Merges cal and diag entries in a single output.
## Config
The config folder contains several .csv files used for RegEx matching.
### setup.log
Used by TesterMonitoringTool to generate the board profiles. Must contain summarized table from any previous diag log.
