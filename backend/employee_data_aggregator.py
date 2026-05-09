import csv
import json
from tqdm import tqdm
from numba import njit

def aggregate_job_change(input_file, lookup_file, output_file):
    csv_data = []
    with open(input_file, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            csv_data.append(row)

    lookup_data = {}


    job_changes = {}
    try:
        with open(output_file, 'r') as file:
            existing_data = json.load(file)
            for participant_id, changes in existing_data.items():
                job_changes[participant_id] = changes
    except FileNotFoundError:
        pass

    for row in csv_data:
        participant_id = row['participantId']
        job_id = row['jobId']
        timestamp = row['timestamp']
        
        if participant_id not in job_changes:
            job_changes[participant_id] = []
        
        if not lookup_data:
            with open(lookup_file, 'r') as file:
                reader = csv.DictReader(file)
                for lookup_row in reader:
                    lookup_data[lookup_row['jobId']] = lookup_row['employerId']
        try:
            
            current_employer_id = lookup_data.get(job_id)
            if current_employer_id is None:
                continue

            # Only add if employerId differs from the previous one
            if job_changes[participant_id]:
                previous_job_id = job_changes[participant_id][-1]['target']
                previous_employer_id = lookup_data.get(previous_job_id, previous_job_id)

                if previous_employer_id != current_employer_id:
                    job_changes[participant_id].append({
                        'source': previous_employer_id,
                        'target': current_employer_id,
                        'timestamp': timestamp
                    })
            else:
                job_changes[participant_id].append({
                'source': None,
                'target': current_employer_id,
                'timestamp': timestamp
                })
        except KeyError:
            continue
    # Remove entries where source is None
    job_changes_new = {}
    for participant_id in job_changes:
        seen = set()
        filtered_changes = []
        for change in job_changes[participant_id]:
            if change['source'] is not None:
                key = (change['source'], change['target'])
                if key not in seen:
                    filtered_changes.append(change)
                    seen.add(key)
        job_changes_new[participant_id] = filtered_changes
        if len(job_changes_new[participant_id]) == 0:
            del job_changes_new[participant_id]
    
    # Sort job changes by timestamp for each participant
    for participant_id in job_changes_new:
        job_changes_new[participant_id].sort(key=lambda x: x['timestamp'])
    
    with open(output_file, 'w') as file:
        json.dump(job_changes_new, file, indent=2)

if __name__ == "__main__":
    input_files = [f"../VAST-Challenge-2022/Datasets/Activity Logs/ParticipantStatusLogs{i}.csv" for i in range (1, 73)]
    lookup_file = "../VAST-Challenge-2022/Datasets/Attributes/Jobs.csv"
    output_files = "job_changes.json"
    for input_file in tqdm(range(len(input_files))):
        aggregate_job_change(input_files[input_file], lookup_file=lookup_file, output_file=output_files)
    
