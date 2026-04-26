import csv
import json
from tqdm import tqdm
from numba import njit

@njit(parallel=True)
def aggregate_job_change(input_file, output_file):
    csv_data = []
    with open(input_file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            csv_data.append(row)
    
    job_changes = {}
    for row in csv_data:
        participant_id = row['participantId']
        job_id = row['jobId']
        timestamp = row['timestamp']
        
        if participant_id not in job_changes:
            job_changes[participant_id] = []
        if not any(entry['jobId'] == job_id for entry in job_changes[participant_id]):
            job_changes[participant_id].append({'jobId': job_id, 'timestamp': timestamp})
    
    # Sort job changes by timestamp for each participant
    for participant_id in job_changes:
        job_changes[participant_id].sort(key=lambda x: x['timestamp'])
    
    with open(output_file, 'w') as file:
        json.dump(job_changes, file, indent=2)

if __name__ == "__main__":
    input_files = [f"../VAST-Challenge-2022/Datasets/Activity Logs/ParticipantStatusLogs{i}.csv" for i in range (1, 73)]
    output_files = [f"job_changes_{i}.json" for i in range (1, 73)]
    for input_file, output_file in tqdm(zip(input_files, output_files), total=len(input_files)):
        aggregate_job_change(input_file, output_file)
    
