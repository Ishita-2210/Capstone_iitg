# Capstone_iitg
Real-Time Dynamic Parking Pricing
This project uses Pathway, a real-time data processing tool, to calculate dynamic parking prices based on current demand and other real-world factors like traffic, queue length, and vehicle type.

 What This Project Does
Reads parking data from a CSV file (simulated as if it's streaming)

Combines date and time into a proper timestamp

Calculates demand using a formula

Sets prices dynamically based on the demand score

Outputs the results into a .jsonl file for visualization or analysis

 Data Columns Used
From the dataset, we use:

Column	Description
Occupancy	How many spots are currently filled
Capacity	Total number of spots
QueueLength	Number of vehicles waiting
TrafficConditionNearby	Traffic score near the lot
IsSpecialDay	1 if there's a holiday/event
VehicleType	car, bike, or truck
LastUpdatedDate + LastUpdatedTime	Combined into a timestamp

 Demand Function (Core Formula)
We use a weighted formula to calculate a "demand score" for each lot, each moment:

makefile
Copy
Edit
demand = 
    1.0 × (Occupancy / Capacity) +
    0.7 × (QueueLength / max_queue) -
    0.4 × (Traffic / max_traffic) +
    0.6 × IsSpecialDay +
    0.3 × VehicleWeight
VehicleWeight is:

1.0 for car

0.8 for bike

1.5 for truck

The score is clipped between 0 and 2.

 Price Calculation
We set prices based on demand using this formula:

ini
Copy
Edit
price = 10 × (1 + 0.4 × demand)
If demand is 0 → price = ₹10

If demand is 2 → price = ₹18

The higher the demand, the higher the price.

This lets prices adapt in real-time as traffic, queue, and occupancy change.

🛠 How It Works
CSV is loaded using Pathway.

A timestamp column is created by combining date and time.

Max queue and traffic values are calculated for normalization.

We compute demand and price.

Results are saved into output.jsonl — one row per update.

📤 Output Example
json
Copy
Edit
{
  "ts": "2016-12-01 10:45:00",
  "lot_id": "BHMMBMMBX01",
  "demand": 1.4,
  "price": 15.6
}
 Summary
This project simulates how cities can:

Set fair and responsive parking prices

Reduce traffic and waiting time

Encourage smarter use of parking spots

It shows how even simple formulas can support smart city infrastructure using real-time data.
