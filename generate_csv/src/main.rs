use chrono::{DateTime, Utc};
use rand::prelude::*;
use serde::{Deserialize, Serialize};
use time::Time;
use time::macros::time;

// Helper Functions to generate random data.
fn get_rand_category(rng: &mut ThreadRng) -> String {
    let cat = vec!["Groceries", "Rent", "Fun", "Transportation"];
    cat[rng.random_range(0..cat.len())].into()
}

fn get_rand_purpose(rng: &mut ThreadRng) -> String {
    let purposes = vec!["Work", "College", "Leisure"];
    purposes[rng.random_range(0..purposes.len())].into()
}

fn get_rand_financial_status(rng: &mut ThreadRng) -> String {
    let purposes = vec!["Employed", "Studying", "Unemployed"];
    purposes[rng.random_range(0..purposes.len())].into()
}

#[derive(Serialize, Deserialize)]
struct ParticipantStatusLog {
    #[serde(rename = "participantId")]
    participant_id: i32,
    timestamp: DateTime<Utc>,
    #[serde(rename = "financialStatus")]
    financial_status: String,
    #[serde(rename = "dailyFoodBudget")]
    daily_food_budget: f32,
    #[serde(rename = "weeklyExtraBudget")]
    weekly_extra_budget: f32,
}
impl ParticipantStatusLog {
    pub fn generate_random(nr_participants: i32, rng: &mut ThreadRng) -> Vec<ParticipantStatusLog> {
        let mut ret = Vec::<ParticipantStatusLog>::new();
        for i in 0..nr_participants {
            let p = ParticipantStatusLog {
                daily_food_budget: rng.random_range(10.0..50.0),
                financial_status: get_rand_financial_status(rng),
                participant_id: i,
                timestamp: Utc::now(),
                weekly_extra_budget: rng.random_range(0.0..500.0),
            };
            ret.push(p);
        }
        ret
    }
}

#[derive(Serialize, Deserialize)]
struct Apartment {
    #[serde(rename = "apartmentId")]
    apartment_id: i32,
    #[serde(rename = "rentalCost")]
    rental_cost: f32,
    #[serde(rename = "buildingId")]
    building_id: i32,
}

#[derive(Serialize, Deserialize)]
struct Building {
    #[serde(rename = "buildingId")]
    building_id: i32,
    #[serde(rename = "buildingType")]
    building_type: String,
    units: Vec<i32>,
}

#[derive(Serialize, Deserialize)]
struct Employer {
    #[serde(rename = "employerId")]
    employer_id: i32,
    #[serde(rename = "buildingId")]
    building_id: i32,
}

#[derive(Serialize, Deserialize)]
struct Job {
    #[serde(rename = "jobId")]
    job_id: i32,
    #[serde(rename = "employerId")]
    employer_id: i32,
    #[serde(rename = "hourlyRate")]
    hourly_rate: f32,
    #[serde(rename = "startTime")]
    start_time: Time,
    #[serde(rename = "endTime")]
    end_time: Time,
    #[serde(rename = "daysToWork")]
    days_to_work: Vec<String>,
    #[serde(rename = "educationRequirement")]
    education_requirement: String,
}

#[derive(Serialize, Deserialize)]
struct Participant {
    #[serde(rename = "participantId")]
    participant_id: i32,
    joviality: f32,
}

#[derive(Serialize, Deserialize)]
struct FinancialJournal {
    #[serde(rename = "participantId")]
    participant_id: i32,
    timestamp: DateTime<Utc>,
    category: String,
    amount: f64,
}
impl FinancialJournal {
    pub fn generate_random(num_participants: i32, rng: &mut ThreadRng) -> Vec<FinancialJournal> {
        let mut ret = Vec::<FinancialJournal>::new();
        for i in 0..num_participants {
            for _ in 0..50 {
                let f = FinancialJournal {
                    amount: rng.random_range(0.5..100.0),
                    category: get_rand_category(rng),
                    participant_id: i,
                    timestamp: Utc::now(),
                };
                ret.push(f);
            }
        }
        ret
    }
}
#[derive(Serialize, Deserialize)]
struct TravelJournal {
    #[serde(rename = "participantId")]
    participant_id: i32,
    purpose: String,
    #[serde(rename = "checkOutTime")]
    check_out_time: DateTime<Utc>,
    #[serde(rename = "travelEndLocation")]
    travel_end_location: i32,
    #[serde(rename = "startingBalance")]
    starting_balance: f64,
    #[serde(rename = "endingBalance")]
    ending_balance: f64,
}

fn generate_participants(n: i32, rng: &mut ThreadRng) -> Vec<Participant> {
    let mut ret: Vec<Participant> = Vec::new();
    for i in 0..n {
        let p = Participant {
            participant_id: i,
            joviality: rng.random_range(0.0..=1.0),
        };

        ret.push(p);
    }
    ret
}

// Returns a tuple with Buildings and Apartments.
// Since Buildings have apartments, it was easier to generate
// directly.
fn generate_buildings(n: i32, rng: &mut ThreadRng) -> (Vec<Building>, Vec<Apartment>) {
    let mut buildings = Vec::<Building>::new();
    let mut apts = Vec::<Apartment>::new();

    for i in 0..n {
        let curr_apt_idx = apts.len();
        let mut this_building_apts = Vec::<i32>::new();
        // Assuming that each building has only 20 apts.
        for e in curr_apt_idx..curr_apt_idx + 20 {
            let apt = Apartment {
                apartment_id: e as i32,
                building_id: i,
                // Let's put some real values for luxembourg.
                rental_cost: rng.random_range(850.0..2000.0),
            };
            this_building_apts.push(apt.apartment_id);
            apts.push(apt);
        }

        let p = Building {
            building_id: i,
            units: this_building_apts,
            building_type: "Comercial".into(),
        };

        buildings.push(p);
    }

    (buildings, apts)
}

fn generate_employer(n: i32, num_buildings: i32, rng: &mut ThreadRng) -> Vec<Employer> {
    let mut ret = Vec::<Employer>::new();
    for i in 0..n {
        let e = Employer {
            employer_id: i as i32,
            building_id: rng.random_range(0..num_buildings),
        };
        ret.push(e);
    }
    ret
}

fn weekdays() -> Vec<String> {
    let ret: Vec<String> = vec![
        String::from("mon"),
        String::from("tue"),
        String::from("wed"),
        String::from("thru"),
        String::from("friday"),
    ];

    ret
}

fn generate_jobs(n: i32, num_employers: i32, rng: &mut ThreadRng) -> Vec<Job> {
    let start_time = time!(8:00);
    let end_time = time!(18:00);
    let mut ret = Vec::<Job>::new();
    for i in 0..n {
        let j = Job {
            job_id: i,
            employer_id: rng.random_range(0..num_employers),
            start_time: start_time,
            end_time: end_time,
            hourly_rate: rng.random_range(8.50..100.0),
            days_to_work: weekdays(),
            // TODO: Improve this.
            education_requirement: String::from("College"),
        };
        ret.push(j);
    }
    ret
}

// Unsure if building or apartment for the travel_end_location.
// Using building.
fn generate_travel_journal(
    num_participants: i32,
    num_buildings: i32,
    rng: &mut ThreadRng,
) -> Vec<TravelJournal> {
    let mut ret: Vec<TravelJournal> = Vec::<TravelJournal>::new();
    for p in 0..num_participants {
        // 50 log entries per person
        for _ in 0..50 {
            let time = Utc::now();
            let t = TravelJournal {
                participant_id: p,
                purpose: get_rand_purpose(rng),
                starting_balance: 100.0,
                ending_balance: rng.random_range(0.0..=100.0),
                check_out_time: time,
                travel_end_location: rng.random_range(0..=num_buildings),
            };
            ret.push(t);
        }
    }
    ret
}

fn save_csv<T>(filename: &str, data: &Vec<T>)
where T: serde::Serialize {
    let mut wtr = csv::Writer::from_path(filename)
        .expect("Could not open file");

    for d in data {
        wtr.serialize(d)
            .expect("Could not serialize data");
    }
    wtr.flush()
        .expect("Could not write file in disk")
}

fn main() {
    let mut rng = rand::rng();

    // Generate 100 participants:
    let participants: Vec<Participant> = generate_participants(100, &mut rng);
    save_csv("participants.csv", &participants);

    let (buildings, apts) = generate_buildings(50, &mut rng);
    save_csv("buildings.csv", &buildings);
    save_csv("apartments.csv", &apts);

    let employers = generate_employer(15, buildings.len() as i32, &mut rng);
    save_csv("employers.csv", &employers);

    // Create less jobs than population so some people don't have jobs.
    let jobs = generate_jobs(90, employers.len() as i32, &mut rng);
    save_csv("jobs.csv", &jobs);

    let travel_journal =
        generate_travel_journal(participants.len() as i32, buildings.len() as i32, &mut rng);
    save_csv("traveljournal.csv", &travel_journal);
    
    let financial_journal = FinancialJournal::generate_random(participants.len() as i32, &mut rng);
    save_csv("financialjournal.csv", &financial_journal);
    
    for i in 0..10 {
        let participant_status =
            ParticipantStatusLog::generate_random(participants.len() as i32, &mut rng);
        let filename = format!("participantStatusLog{}", i);
        save_csv(&filename, &participant_status);
    }

    // I Might have not undertstood the `N` in the ParticipantStatusLog<N>.
    // is the N for one participant? if so, I don't see the need to store it's id.
    // Is it for Weekly data? A bit confusing.

}
