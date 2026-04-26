import csv
import json

def csv_to_json(csv_file, json_file):
    data = []
    with open(csv_file, encoding='utf-8') as csvf:
        csv_reader = csv.DictReader(csvf)
        csv_reader.fieldnames = [field.strip() for field in csv_reader.fieldnames]  # Strip whitespace from field names
        rows = list(csv_reader)
        cleansed_rows = []
        for row in rows:
            row['coords'] = polygon_parser(row['location'])
            row.pop('location', None)  # Remove the original 'location' field
            row.pop("maxOccupancy", None)  # Remove the 'maxOccupancy' field
            row.pop("units", None)
            row["id"] = row["buildingId"]  # Rename 'buildingID' to 'id'
            row.pop("buildingId", None)  # Remove the original 'buildingID' field
            data.append(row)

    with open(json_file, 'w', encoding='utf-8') as jsonf:
        jsonf.write(json.dumps(data, indent=4))

def polygon_parser(polygon_str):
    # Remove the "POLYGON ((" and "))" parts
    polygon_str = polygon_str.replace("POLYGON ((", "").replace(")", "").replace("(", "")
    # Split the string into coordinate pairs
    coordinate_pairs = polygon_str.split(", ")
    # Convert each pair into a list of floats
    coordinates = []
    for pair in coordinate_pairs:
        x, y = map(float, pair.split())
        coordinates.append([x, y])
    return coordinates

if __name__ == "__main__":
    csv_file = '../VAST-Challenge-2022/Datasets/Attributes/Buildings.csv'  # Path to your CSV file
    json_file = 'buildings.json'  # Path to the output JSON file
    csv_to_json(csv_file, json_file)