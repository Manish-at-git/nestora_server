"""Curated non-India geography and the pinned India source metadata."""

INDIA_DATASET_URL = (
    "https://raw.githubusercontent.com/CodingMation/indian-states-districts/"
    "3d2c4290b9c2040dc3a9c66597f4b0f88f11385d/data/india_states_districts.min.json"
)
INDIA_DATASET_SHA256 = "baf2d42e6a3c1a35da2120f1e19bfbebaf742de37600a33e62df07c8444bc218"

COUNTRIES = (
    ("IN", "IND", "India", "INR"),
    ("US", "USA", "United States", "USD"),
    ("GB", "GBR", "United Kingdom", "GBP"),
    ("CA", "CAN", "Canada", "CAD"),
    ("AU", "AUS", "Australia", "AUD"),
    ("AE", "ARE", "United Arab Emirates", "AED"),
    ("SG", "SGP", "Singapore", "SGD"),
    ("SA", "SAU", "Saudi Arabia", "SAR"),
    ("DE", "DEU", "Germany", "EUR"),
    ("FR", "FRA", "France", "EUR"),
    ("JP", "JPN", "Japan", "JPY"),
)

# country ISO2, region code, region name, region type, district code, district name, city name
MAJOR_WORLD_CITIES = (
    ("US", "CA", "California", "STATE", "LOS_ANGELES", "Los Angeles County", "Los Angeles"),
    ("US", "CA", "California", "STATE", "SAN_FRANCISCO", "San Francisco County", "San Francisco"),
    ("US", "NY", "New York", "STATE", "NEW_YORK", "New York County", "New York City"),
    ("US", "TX", "Texas", "STATE", "HARRIS", "Harris County", "Houston"),
    ("US", "IL", "Illinois", "STATE", "COOK", "Cook County", "Chicago"),
    ("GB", "ENG", "England", "COUNTRY", "GREATER_LONDON", "Greater London", "London"),
    ("GB", "SCT", "Scotland", "COUNTRY", "GLASGOW_CITY", "Glasgow City", "Glasgow"),
    ("GB", "WLS", "Wales", "COUNTRY", "CARDIFF", "Cardiff", "Cardiff"),
    ("CA", "ON", "Ontario", "PROVINCE", "TORONTO", "Toronto", "Toronto"),
    ("CA", "BC", "British Columbia", "PROVINCE", "METRO_VANCOUVER", "Metro Vancouver", "Vancouver"),
    ("CA", "QC", "Quebec", "PROVINCE", "MONTREAL", "Montreal", "Montreal"),
    ("AU", "NSW", "New South Wales", "STATE", "SYDNEY", "Sydney", "Sydney"),
    ("AU", "VIC", "Victoria", "STATE", "MELBOURNE", "Melbourne", "Melbourne"),
    ("AU", "QLD", "Queensland", "STATE", "BRISBANE", "Brisbane", "Brisbane"),
    ("AE", "DU", "Dubai", "EMIRATE", "DUBAI", "Dubai", "Dubai"),
    ("AE", "AZ", "Abu Dhabi", "EMIRATE", "ABU_DHABI", "Abu Dhabi", "Abu Dhabi"),
    ("SG", "SG", "Singapore", "CITY_STATE", "SINGAPORE", "Singapore", "Singapore"),
    ("SA", "RIY", "Riyadh", "PROVINCE", "RIYADH", "Riyadh", "Riyadh"),
    ("SA", "MKK", "Makkah", "PROVINCE", "JEDDAH", "Jeddah", "Jeddah"),
    ("DE", "BE", "Berlin", "STATE", "BERLIN", "Berlin", "Berlin"),
    ("DE", "BY", "Bavaria", "STATE", "MUNICH", "Munich", "Munich"),
    ("DE", "HH", "Hamburg", "STATE", "HAMBURG", "Hamburg", "Hamburg"),
    ("FR", "IDF", "Ile-de-France", "REGION", "PARIS", "Paris", "Paris"),
    ("FR", "ARA", "Auvergne-Rhone-Alpes", "REGION", "RHONE", "Rhone", "Lyon"),
    ("FR", "PACA", "Provence-Alpes-Cote d'Azur", "REGION", "BOUCHES_DU_RHONE", "Bouches-du-Rhone", "Marseille"),
    ("JP", "TK", "Tokyo", "PREFECTURE", "TOKYO", "Tokyo", "Tokyo"),
    ("JP", "OS", "Osaka", "PREFECTURE", "OSAKA", "Osaka", "Osaka"),
    ("JP", "KN", "Kanagawa", "PREFECTURE", "YOKOHAMA", "Yokohama", "Yokohama"),
)

# India entries use the state and district codes in the pinned source above.
INDIA_MAJOR_CITIES = (
    ("AN", "SOUTH_ANDAMAN", "Port Blair"), ("AP", "VISAKHAPATNAM", "Visakhapatnam"),
    ("AP", "NTR", "Vijayawada"), ("AR", "PAPUM_PARE", "Itanagar"), ("AS", "KAMRUP_METROPOLITAN", "Guwahati"),
    ("BR", "PATNA", "Patna"), ("CH", "CHANDIGARH", "Chandigarh"), ("CT", "RAIPUR", "Raipur"),
    ("DH", "DAMAN", "Daman"), ("DL", "NEW_DELHI", "New Delhi"), ("GA", "NORTH_GOA", "Panaji"),
    ("GJ", "AHMEDABAD", "Ahmedabad"), ("GJ", "SURAT", "Surat"), ("GJ", "VADODARA", "Vadodara"),
    ("HR", "GURUGRAM", "Gurugram"),
    ("HP", "SHIMLA", "Shimla"), ("JH", "RANCHI", "Ranchi"), ("JK", "JAMMU", "Jammu"),
    ("JK", "SRINAGAR", "Srinagar"), ("KA", "BENGALURU_URBAN", "Bengaluru"),
    ("KL", "THIRUVANANTHAPURAM", "Thiruvananthapuram"), ("LA", "LEH", "Leh"),
    ("LD", "LAKSHADWEEP", "Kavaratti"), ("MH", "MUMBAI_CITY", "Mumbai"), ("MH", "PUNE", "Pune"),
    ("MH", "NAGPUR", "Nagpur"), ("ML", "EAST_KHASI_HILLS", "Shillong"), ("MN", "IMPHAL_WEST", "Imphal"),
    ("MP", "BHOPAL", "Bhopal"), ("MZ", "AIZAWL", "Aizawl"), ("NL", "KOHIMA", "Kohima"),
    ("OR", "KHORDHA", "Bhubaneswar"), ("PB", "LUDHIANA", "Ludhiana"), ("PY", "PUDUCHERRY", "Puducherry"),
    ("RJ", "JAIPUR", "Jaipur"), ("RJ", "JODHPUR", "Jodhpur"), ("SK", "EAST_SIKKIM", "Gangtok"),
    ("TN", "CHENNAI", "Chennai"), ("TN", "COIMBATORE", "Coimbatore"), ("TS", "HYDERABAD", "Hyderabad"),
    ("TR", "WEST_TRIPURA", "Agartala"), ("UK", "DEHRADUN", "Dehradun"), ("UP", "LUCKNOW", "Lucknow"),
    ("UP", "KANPUR_NAGAR", "Kanpur"), ("UP", "VARANASI", "Varanasi"), ("WB", "KOLKATA", "Kolkata"),
)
