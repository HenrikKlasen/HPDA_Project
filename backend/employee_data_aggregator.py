import csv
import json
from tqdm import tqdm
from numba import njit

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
        
        # Only add if jobId differs from the previous one
        if job_changes[participant_id]:
            previous_job = job_changes[participant_id][-1]['target']
            if previous_job != job_id:
                job_changes[participant_id].append({
                    'source': previous_job,
                    'target': job_id,
                    'timestamp': timestamp
                })
        else:
            # First entry for this participant, no source job
            job_changes[participant_id].append({
                'source': None,
                'target': job_id,
                'timestamp': timestamp
            })
    
    # Remove entries where source is None
    job_changes_new = {}
    for participant_id in job_changes:
        job_changes_new[participant_id] = [
            change for change in job_changes[participant_id] if change['source'] is not None
        ]
        if len(job_changes_new[participant_id]) == 0:
            del job_changes_new[participant_id]
    
    # Sort job changes by timestamp for each participant
    for participant_id in job_changes_new:
        job_changes_new[participant_id].sort(key=lambda x: x['timestamp'])
    
    with open(output_file, 'a') as file:
        json.dump(job_changes_new, file, indent=2)

if __name__ == "__main__":
    input_files = [f"../VAST-Challenge-2022/Datasets/Activity Logs/ParticipantStatusLogs{i}.csv" for i in range (1, 73)]
    output_files = "job_changes.json"
    for input_file in tqdm(range(len(input_files))):
        aggregate_job_change(input_files[input_file], output_file=output_files)
    
