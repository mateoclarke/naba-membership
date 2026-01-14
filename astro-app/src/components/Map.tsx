import { useEffect, useRef } from 'react';
import type L from 'leaflet';

interface MapProps {
	memberCounts: Record<string, number>;
	statsData: {
		total: number;
		states: Record<string, number>;
		canada: number;
		international: number;
	};
	stateMapping: Record<string, string>;
}

export default function Map({ memberCounts, statsData, stateMapping }: MapProps) {
	const mapRef = useRef<L.Map | null>(null);
	const mapContainerRef = useRef<HTMLDivElement>(null);
	const geojsonRef = useRef<L.GeoJSON | null>(null);

	useEffect(() => {
		if (!mapContainerRef.current || mapRef.current) return;

		// Initialize map
		const map = (window as any).L.map(mapContainerRef.current).setView([39.8283, -98.5795], 4);
		mapRef.current = map;

		// Add tile layer
		(window as any).L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
			maxZoom: 19,
			attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
		}).addTo(map);

		// Helper function to get state code from feature
		function getStateCode(feature: any): string | null {
			if (feature.properties.STUSPS) return feature.properties.STUSPS;
			if (feature.properties.STATE) return feature.properties.STATE;
			if (feature.properties.state) return feature.properties.state.toUpperCase();
			if (feature.properties.name) {
				const code = stateMapping[feature.properties.name];
				if (code) return code;
			}
			return null;
		}

		// Color function based on member count
		function getColor(count: number): string {
			if (!count || count === 0) return '#f7f7f7';
			return count > 25 ? '#800026' :
				count > 15 ? '#BD0026' :
				count > 10 ? '#E31A1C' :
				count > 5 ? '#FC4E2A' :
				count > 2 ? '#FD8D3C' :
				count > 0 ? '#FED976' :
				'#f7f7f7';
		}

		// Style function for GeoJSON features
		function style(feature: any) {
			const stateCode = getStateCode(feature);
			const count = stateCode ? (memberCounts[stateCode] || 0) : 0;

			return {
				fillColor: getColor(count),
				weight: 2,
				opacity: 1,
				color: 'white',
				dashArray: '3',
				fillOpacity: 0.7
			};
		}

		// Create info control
		const info = (window as any).L.control();
		info.onAdd = function (map: L.Map) {
			const div = (window as any).L.DomUtil.create('div', 'info');
			div.innerHTML = '<h4>Active Members by State</h4>Hover over a state';
			return div;
		};
		info.update = function (props?: { name: string; count: number }) {
			if (props) {
				this._div.innerHTML = '<h4>Active Members by State</h4>' +
					'<b>' + props.name + '</b><br />' + props.count + ' active member' + (props.count !== 1 ? 's' : '');
			} else {
				this._div.innerHTML = '<h4>Active Members by State</h4>Hover over a state';
			}
		};
		info.addTo(map);

		// Create legend control
		const legend = (window as any).L.control({ position: 'bottomright' });
		legend.onAdd = function (map: L.Map) {
			const div = (window as any).L.DomUtil.create('div', 'info legend');
			const grades = [0, 1, 3, 6, 11, 16, 26];
			for (let i = 0; i < grades.length; i++) {
				div.innerHTML +=
					'<i style="background:' + getColor(grades[i] + 1) + '"></i> ' +
					grades[i] + (grades[i + 1] ? '&ndash;' + grades[i + 1] + '<br>' : '+');
			}
			return div;
		};
		legend.addTo(map);

		// Create statistics panel control
		const stats = (window as any).L.control({ position: 'topleft' });
		stats.onAdd = function (map: L.Map) {
			const div = (window as any).L.DomUtil.create('div', 'stats');

			let html = '<h4>Active Members</h4>';
			html += '<div class="total">Total: ' + statsData.total + '</div>';

			// US States section - sorted by count (descending)
			html += '<div class="section">';
			html += '<div class="section-title">US States:</div>';
			const states = statsData.states;
			const stateEntries = Object.keys(states).map(stateCode => [stateCode, states[stateCode]]);
			stateEntries.sort((a, b) => (b[1] as number) - (a[1] as number));

			for (let i = 0; i < stateEntries.length; i++) {
				const stateCode = stateEntries[i][0];
				const count = stateEntries[i][1];
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
			(window as any).L.DomEvent.disableScrollPropagation(div);
			(window as any).L.DomEvent.on(div, 'mousewheel', (window as any).L.DomEvent.stopPropagation);
			(window as any).L.DomEvent.on(div, 'DOMMouseScroll', (window as any).L.DomEvent.stopPropagation);

			return div;
		};
		stats.addTo(map);

		// Event handlers
		function highlightFeature(e: L.LeafletMouseEvent) {
			const layer = e.target;
			layer.setStyle({
				weight: 5,
				color: '#666',
				dashArray: '',
				fillOpacity: 0.7
			});

			if (!(window as any).L.Browser.ie && !(window as any).L.Browser.opera && !(window as any).L.Browser.edge) {
				layer.bringToFront();
			}

			const stateCode = getStateCode(layer.feature);
			const stateName = layer.feature.properties.NAME || layer.feature.properties.name || stateCode || 'Unknown';
			const count = stateCode ? (memberCounts[stateCode] || 0) : 0;

			info.update({
				name: stateName,
				count: count
			});
		}

		function resetHighlight(e: L.LeafletMouseEvent) {
			if (geojsonRef.current) {
				geojsonRef.current.resetStyle(e.target);
			}
			info.update();
		}

		function zoomToFeature(e: L.LeafletMouseEvent) {
			map.fitBounds(e.target.getBounds());
		}

		function onEachFeature(feature: any, layer: L.Layer) {
			layer.on({
				mouseover: highlightFeature,
				mouseout: resetHighlight,
				click: zoomToFeature
			});
		}

		// Load US states GeoJSON
		fetch('https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json')
			.then(response => response.json())
			.then(data => {
				const geojson = (window as any).L.geoJson(data, {
					style: style,
					onEachFeature: onEachFeature
				}).addTo(map);
				geojsonRef.current = geojson;
			})
			.catch(error => {
				console.error('Error loading GeoJSON:', error);
				alert('Failed to load map data. Please check your internet connection.');
			});

		return () => {
			if (mapRef.current) {
				mapRef.current.remove();
				mapRef.current = null;
			}
		};
	}, [memberCounts, statsData, stateMapping]);

	return <div id="map" ref={mapContainerRef}></div>;
}
