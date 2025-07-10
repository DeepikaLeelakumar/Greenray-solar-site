// 1. Initialize the map
const map = L.map('map', {
  scrollWheelZoom: true,
  dragging: true,
  tap: false
});

// 2. Set tile layer (OpenStreetMap tiles)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// 3. Site data (coordinates, address, and image)
const solarSites = [
  {
    name: "PMSR001",
    coords: [12.940314, 80.067535],
    address: "Plot No.9, Anthoniyar Nagar, Thirumudivakkam, Chennai 600132",
    System_Capacity : "3KW",
    Type: "GIE",
    img: "assests/assests.pmsr1.png"
  },
  {
    name: "PMSR002",
    coords: [12.9444530, 80.2551347],
    address: "No 9A Beach Walk G Square, Neelankarai, Chennai 600115",
    System_Capacity : "3KW",
    Type: "Minirail",
    img: "assests/pmsr002.png"
  },
  {
    name: "PMSR003",
    coords: [12.8829, 80.1218],
    address: "1B, RR Gokulam, Kozapakkam, Vandalur, Chennai 600127",
    System_Capacity : "3KW",
    Type: "GIE Customized",
    img: "assests/pmsr003.png"
  },
  {
    name: "PMSR004",
    coords: [13.2126, 80.2784],
    address: "90, Manali New Town, Thiruvottiyur, Chennai 600103",
    System_Capacity : "2KW",
    Type: "GIE",
    img: "assests/Screenshot 2025-07-09 132010.png"
  },
  {
    name: "PMSR005",
    coords: [13.118, 80.1593],
    address: "13/5 Upper Canal Rd, Prithivipakkam, Ambattur, Chennai 600053",
    System_Capacity : "4KW",
    Type: "GIE Customized",
    img: "assests/pmsr005.png"
  }
];

// 4. Add markers and popups
solarSites.forEach(site => {
  L.marker(site.coords)
    .addTo(map)
    .bindPopup(`
      <b>${site.name}</b><br>
      <img src="${site.img}" alt="${site.name}" width="200px" style="margin-top:8px; border-radius:6px;" /><br>
      <strong>Address:</strong> ${site.address}<br>
      <strong>System Capacity:</strong> ${site.System_Capacity}<br>
      <strong>System Type:</strong> ${site.Type}<br>
      
    `);
});

// 5. Auto-zoom the map to fit all site locations
const allCoords = solarSites.map(site => site.coords);
map.fitBounds(allCoords);

