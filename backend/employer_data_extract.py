import csv
import json
from tqdm import tqdm

def convert_employer_data(input_file, output_file):
    employers = []
    with open(input_file, 'r') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            employers.append({
                'employerId': row['employerId'],
                'name': row['name'],
                'x': row['location']
            })
    
    with open(output_file, 'w') as file:
        json.dump(employers, file, indent=2)

def point_parser(point_str):
    # Remove the "POLYGON ((" and "))" parts
    point_str = point_str.replace("POINT (", "").replace(")", "")
    # Split the string into coordinate pairs
    coordinate_pairs = point_str.split(", ")
    # Convert each pair into a list of floats
    coordinates = [list(map(float, pair.split())) for pair in coordinate_pairs]
    return coordinates[0], coordinates[1]