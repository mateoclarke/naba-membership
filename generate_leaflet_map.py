#!/usr/bin/env python3
"""
Generate Leaflet Choropleth Map HTML from CSV data
Creates a standalone HTML file with embedded member data.
"""

import pandas as pd
import json
import sys
import os


def generate_leaflet_html(csv_file, output_file=None):
    """
    Generate a Leaflet choropleth map HTML file from CSV data.
    
    Args:
        csv_file: Path to the cleaned CSV file
        output_file: Output HTML file path (optional, defaults to "NaBA Member Data Viz/index.html")
    """
    # Set default output directory and file
    output_dir = "NaBA Member Data Viz"
    if output_file is None:
        output_file = os.path.join(output_dir, "index.html")
    else:
        # If output_file is provided, ensure it's in the output directory
        output_file = os.path.join(output_dir, os.path.basename(output_file))
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    # Read the CSV - try multiple encodings
    print(f"Reading data from {csv_file}...")
    encodings = ['utf-8', 'iso-8859-1', 'latin-1', 'cp1252', 'windows-1252']
    df = None
    
    for encoding in encodings:
        try:
            df = pd.read_csv(csv_file, encoding=encoding)
            print(f"Successfully read CSV with encoding: {encoding}")
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"Error reading with {encoding}: {e}")
            continue
    
    if df is None:
        raise ValueError(f"Could not read CSV file with any of the attempted encodings: {encodings}")
    
    # Filter for all active members
    all_active = df[df['status'] == 'active'].copy()
    total_active = len(all_active)
    
    # Filter for active US members with state data
    us_active = all_active[
        (all_active['mepr-address-country'] == 'US') & 
        (all_active['mepr-address-state'].notna())
    ].copy()
    
    # Count members by state
    # Normalize state codes - handle variations like "NEW YORK" -> "NY"
    state_normalized = us_active['mepr-address-state'].str.upper().str.strip()
    
    # Map common state name variations to codes
    state_name_to_code_map = {
        'NEW YORK': 'NY', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW HAMPSHIRE': 'NH',
        'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'SOUTH CAROLINA': 'SC', 'SOUTH DAKOTA': 'SD',
        'WEST VIRGINIA': 'WV', 'RHODE ISLAND': 'RI', 'DISTRICT OF COLUMBIA': 'DC'
    }
    
    # Replace full state names with codes
    for full_name, code in state_name_to_code_map.items():
        state_normalized = state_normalized.replace(full_name, code)
    
    state_counts = state_normalized.value_counts()
    member_counts_dict = state_counts.to_dict()
    
    # Count Canada members - check for both "CA" code and "Canada" name
    country_normalized = all_active['mepr-address-country'].str.upper().str.strip()
    canada_active = all_active[
        (country_normalized == 'CA') | 
        (country_normalized == 'CANADA')
    ].copy()
    canada_count = len(canada_active)
    
    # Count other international members (not US, not Canada)
    international_active = all_active[
        (all_active['mepr-address-country'].notna()) &
        (country_normalized != 'US') &
        (country_normalized != 'CA') &
        (country_normalized != 'CANADA')
    ].copy()
    international_count = len(international_active)
    
    print(f"\nActive members by state:")
    for state, count in sorted(member_counts_dict.items()):
        print(f"  {state}: {count}")
    print(f"\nCanada: {canada_count}")
    print(f"International: {international_count}")
    print(f"\nTotal active members: {total_active}")
    
    # Convert to JavaScript object format
    js_member_counts = json.dumps(member_counts_dict, indent=2)
    
    # Create statistics object for the panel
    stats_data = {
        'total': total_active,
        'states': dict(sorted(member_counts_dict.items())),
        'canada': canada_count,
        'international': international_count
    }
    js_stats = json.dumps(stats_data, indent=2)
    
    # State name to code mapping
    state_name_to_code = {
        "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
        "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
        "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
        "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
        "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
        "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
        "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
        "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
        "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
        "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
        "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
        "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
        "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC"
    }
    js_state_mapping = json.dumps(state_name_to_code, indent=2)
    
    # Read the HTML template
    html_template = '''<!DOCTYPE html>
<html>
<head>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>Active Members by State - Choropleth Map</title>
	
	<!-- Leaflet CSS -->
	<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
		integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
		crossorigin=""/>
	
	<style>
		body {
			margin: 0;
			padding: 0;
			font-family: Arial, Helvetica, sans-serif;
		}
		
		#map {
			width: 100%;
			height: 100vh;
		}
		
		.info {
			padding: 6px 8px;
			font: 14px/16px Arial, Helvetica, sans-serif;
			background: white;
			background: rgba(255,255,255,0.8);
			box-shadow: 0 0 15px rgba(0,0,0,0.2);
			border-radius: 5px;
		}
		
		.info h4 {
			margin: 0 0 5px;
			color: #777;
		}
		
		.legend {
			line-height: 18px;
			color: #555;
		}
		
		.legend i {
			width: 18px;
			height: 18px;
			float: left;
			margin-right: 8px;
			opacity: 0.7;
		}
		
		.stats {
			padding: 10px 12px;
			font: 12px/16px Arial, Helvetica, sans-serif;
			background: white;
			background: rgba(255,255,255,0.95);
			box-shadow: 0 0 15px rgba(0,0,0,0.2);
			border-radius: 5px;
			max-height: 70vh;
			overflow-y: auto;
			min-width: 250px;
		}
		
		.stats h4 {
			margin: 0 0 8px 0;
			color: #333;
			font-size: 14px;
			border-bottom: 2px solid #333;
			padding-bottom: 5px;
		}
		
		.stats .total {
			font-weight: bold;
			font-size: 14px;
			margin: 8px 0;
			color: #000;
		}
		
		.stats .section {
			margin: 10px 0;
		}
		
		.stats .section-title {
			font-weight: bold;
			color: #555;
			margin-top: 8px;
			margin-bottom: 4px;
		}
		
		.stats .state-item {
			display: flex;
			justify-content: space-between;
			padding: 2px 0;
		}
		
		.stats .state-item .state-code {
			font-weight: bold;
			color: #333;
		}
		
		.stats .state-item .state-count {
			color: #666;
		}
		
		/* Prevent scroll events in stats panel from zooming the map */
		.stats {
			-webkit-overflow-scrolling: touch;
		}
	</style>
</head>
<body>
	<div id="map"></div>

	<!-- Leaflet JavaScript -->
	<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
		integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
		crossorigin=""></script>
	
	<script>
		// Member counts by state (generated from CSV)
		var memberCounts = {member_counts_placeholder};
		
		// Statistics data (total, states, canada, international)
		var statsData = {stats_data_placeholder};
		
		// Mapping from state names to state codes
		var stateNameToCode = {state_mapping_placeholder};
		
		// Helper function to get state code from feature
		function getStateCode(feature) {
			// Try different possible property names
			if (feature.properties.STUSPS) return feature.properties.STUSPS;
			if (feature.properties.STATE) return feature.properties.STATE;
			if (feature.properties.state) return feature.properties.state.toUpperCase();
			if (feature.properties.name) {
				// Convert state name to code
				var code = stateNameToCode[feature.properties.name];
				if (code) return code;
			}
			return null;
		}
		
		// Get the maximum count for color scaling
		var maxCount = Math.max(...Object.values(memberCounts));
		
		// Color function based on member count
		// Updated scale for data range 0-36
		function getColor(count) {
			if (!count || count === 0) return '#f7f7f7'; // No members - light gray
			return count > 25 ? '#800026' :  // 26+ members - darkest red
			       count > 15 ? '#BD0026' :  // 16-25 members - dark red
			       count > 10 ? '#E31A1C' :  // 11-15 members - red
			       count > 5  ? '#FC4E2A' :  // 6-10 members - red-orange
			       count > 2  ? '#FD8D3C' :  // 3-5 members - orange
			       count > 0  ? '#FED976' :  // 1-2 members - light yellow
			                  '#f7f7f7';
		}
		
		// Style function for GeoJSON features
		function style(feature) {
			var stateCode = getStateCode(feature);
			var count = stateCode ? (memberCounts[stateCode] || 0) : 0;
			
			return {
				fillColor: getColor(count),
				weight: 2,
				opacity: 1,
				color: 'white',
				dashArray: '3',
				fillOpacity: 0.7
			};
		}
		
		// Highlight feature on hover
		function highlightFeature(e) {
			var layer = e.target;
			
			layer.setStyle({
				weight: 5,
				color: '#666',
				dashArray: '',
				fillOpacity: 0.7
			});
			
			if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {
				layer.bringToFront();
			}
			
			// Update info panel
			var stateCode = getStateCode(layer.feature);
			var stateName = layer.feature.properties.NAME || layer.feature.properties.name || stateCode || 'Unknown';
			var count = stateCode ? (memberCounts[stateCode] || 0) : 0;
			
			info.update({
				name: stateName,
				count: count
			});
		}
		
		// Reset highlight on mouseout
		function resetHighlight(e) {
			geojson.resetStyle(e.target);
			info.update();
		}
		
		// Zoom to feature on click
		function zoomToFeature(e) {
			map.fitBounds(e.target.getBounds());
		}
		
		// Add event listeners to each feature
		function onEachFeature(feature, layer) {
			layer.on({
				mouseover: highlightFeature,
				mouseout: resetHighlight,
				click: zoomToFeature
			});
		}
		
		// Initialize map
		var map = L.map('map').setView([39.8283, -98.5795], 4);
		
		// Add tile layer
		L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
			maxZoom: 19,
			attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
		}).addTo(map);
		
		// Create info control
		var info = L.control();
		
		info.onAdd = function (map) {
			this._div = L.DomUtil.create('div', 'info');
			this.update();
			return this._div;
		};
		
		info.update = function (props) {
			this._div.innerHTML = '<h4>Active Members by State</h4>' +  (props ?
				'<b>' + props.name + '</b><br />' + props.count + ' active member' + (props.count !== 1 ? 's' : '')
				: 'Hover over a state');
		};
		
		info.addTo(map);
		
		// Create legend control
		var legend = L.control({position: 'bottomright'});
		
		legend.onAdd = function (map) {
			var div = L.DomUtil.create('div', 'info legend');
			var grades = [0, 1, 3, 6, 11, 16, 26];
			var labels = [];
			
			// Loop through intervals and generate labels
			for (var i = 0; i < grades.length; i++) {
				div.innerHTML +=
					'<i style="background:' + getColor(grades[i] + 1) + '"></i> ' +
					grades[i] + (grades[i + 1] ? '&ndash;' + grades[i + 1] + '<br>' : '+');
			}
			
			return div;
		};
		
		legend.addTo(map);
		
		// Create statistics panel control
		var stats = L.control({position: 'topleft'});
		
		stats.onAdd = function (map) {
			var div = L.DomUtil.create('div', 'stats');
			
			// Build HTML for statistics
			var html = '<h4>Active Members</h4>';
			html += '<div class="total">Total: ' + statsData.total + '</div>';
			
			// US States section - sorted by count (descending)
			html += '<div class="section">';
			html += '<div class="section-title">US States:</div>';
			var states = statsData.states;
			// Create array of [stateCode, count] pairs and sort by count (descending)
			var stateEntries = Object.keys(states).map(function(stateCode) {
				return [stateCode, states[stateCode]];
			});
			stateEntries.sort(function(a, b) {
				return b[1] - a[1]; // Sort by count descending
			});
			// Display states sorted by count
			for (var i = 0; i < stateEntries.length; i++) {
				var stateCode = stateEntries[i][0];
				var count = stateEntries[i][1];
				html += '<div class="state-item">';
				html += '<span class="state-code">' + stateCode + ':</span> ';
				html += '<span class="state-count">' + count + '</span>';
				html += '</div>';
			}
			html += '</div>';
			
			// Canada section
			if (statsData.canada > 0) {
				html += '<div class="section">';
				html += '<div class="state-item">';
				html += '<span class="state-code">Canada:</span> ';
				html += '<span class="state-count">' + statsData.canada + '</span>';
				html += '</div>';
			}
			
			// International section
			if (statsData.international > 0) {
				html += '<div class="section">';
				html += '<div class="state-item">';
				html += '<span class="state-code">International:</span> ';
				html += '<span class="state-count">' + statsData.international + '</span>';
				html += '</div>';
			}
			
			div.innerHTML = html;
			
			// Prevent scroll events in stats panel from zooming the map
			L.DomEvent.disableScrollPropagation(div);
			L.DomEvent.on(div, 'mousewheel', L.DomEvent.stopPropagation);
			L.DomEvent.on(div, 'DOMMouseScroll', L.DomEvent.stopPropagation);
			
			return div;
		};
		
		stats.addTo(map);
		
		// Load US states GeoJSON from GitHub
		// Using a reliable source for US states GeoJSON
		var geojson;
		fetch('https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json')
			.then(response => response.json())
			.then(data => {
				console.log('GeoJSON loaded successfully');
				console.log('Sample feature properties:', data.features[0].properties);
				// Add GeoJSON layer to map
				geojson = L.geoJson(data, {
					style: style,
					onEachFeature: onEachFeature
				}).addTo(map);
				console.log('GeoJSON layer added to map');
			})
			.catch(error => {
				console.error('Error loading GeoJSON:', error);
				// Alternative source
				fetch('https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json')
					.then(response => response.json())
					.then(data => {
						geojson = L.geoJson(data, {
							style: style,
							onEachFeature: onEachFeature
						}).addTo(map);
					})
					.catch(err => {
						console.error('Failed to load GeoJSON:', err);
						alert('Failed to load map data. Please check your internet connection.');
					});
			});
	</script>
</body>
</html>'''
    
    # Replace placeholders with actual data
    html_content = html_template.replace('{member_counts_placeholder}', js_member_counts)
    html_content = html_content.replace('{stats_data_placeholder}', js_stats)
    html_content = html_content.replace('{state_mapping_placeholder}', js_state_mapping)
    
    # Write HTML file
    print(f"\nGenerating HTML file: {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✓ HTML file created successfully in '{output_dir}/'!")
    print(f"\nOpen {output_file} in your web browser to view the interactive map.")
    print("\nFeatures:")
    print("  - Hover over states to see member counts")
    print("  - Click on states to zoom in")
    print("  - Color-coded by number of active members")
    print("  - Legend shows the color scale")
    
    return output_file


def main():
    """Main function."""
    if len(sys.argv) < 2:
        csv_file = 'members-1768334501_cleaned.csv'
        print(f"No CSV file specified, using default: {csv_file}")
    else:
        csv_file = sys.argv[1]
    
    if not os.path.exists(csv_file):
        print(f"Error: File '{csv_file}' not found.")
        sys.exit(1)
    
    # If output file is specified, use it; otherwise use default (index.html in output dir)
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    generate_leaflet_html(csv_file, output_file)


if __name__ == "__main__":
    main()
