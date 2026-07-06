"""
Find nearest DWD weather station for each of our 10 DB train stations.
Prints station IDs for use in the weather download script.
"""
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst import Parameter, Resolution, Period

DB_STATIONS = {
    "Frankfurt (Main) Hbf": (50.107, 8.662),
    "Berlin Hauptbahnhof": (52.525, 13.369),
    "Muenchen Hbf": (48.140, 11.555),  # avoid umlaut issues
    "Hannover Hbf": (52.376, 9.742),
    "Hamburg Hbf": (53.553, 10.006),
    "Nuernberg Hbf": (49.446, 11.082),
    "Berlin-Spandau": (52.530, 13.197),
    "Koeln Hbf": (50.943, 6.959),
    "Kassel-Wilhelmshoehe": (51.313, 9.448),
    "Duesseldorf Hbf": (51.221, 6.793),
}

request = DwdObservationRequest(
    parameter=[Parameter.TEMPERATURE_AIR_2M],
    resolution=Resolution.HOURLY,
    period=Period.HISTORICAL,
)

print("DB Station -> Nearest DWD Weather Station")
print("="*70)
for city, (lat, lon) in DB_STATIONS.items():
    nearby = request.filter_by_rank(latlon=(lon, lat), rank=1)
    if len(nearby) > 0:
        s = nearby.iloc[0]
        sid = s["station_id"]
        sname = s["name"]
        plat = float(s["latitude"])
        plon = float(s["longitude"])
        dist_km = ((lat - plat)**2 + (lon - plon)**2)**0.5 * 111
        print(f"{city:25s} -> {sname:25s} (ID={sid:>5s}, {dist_km:4.0f} km)")
    else:
        print(f"{city:25s} -> No station found")
