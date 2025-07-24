// 1. Initialize the map
const map = L.map('map', {
  scrollWheelZoom: true,
  dragging: true,
  tap: false
});

// 2. Set tile layer (OpenStreetMap)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// 3. Fetch site data from Flask backend
fetch('/api/sites')
  .then(response => response.json())
  .then(data => {
    const bounds = [];

    data.sites.forEach(site => {
      if (!site.latitude || !site.longitude) return;

      const latLng = [site.latitude, site.longitude];
      bounds.push(latLng);

      // Construct popup content with optional image
      let popupContent = `
        <b>${site.name}</b><br>
        <strong>Address:</strong> ${site.address}<br>
        <strong>System Capacity:</strong> ${site.capacity}<br>
        <strong>System Type:</strong> ${site.type}<br>
      `;

      if (site.image_url) {
        popupContent += `<img src="/static/assets/${site.image_url}" width="200" height="150" style="margin-top: 5px;" />`;
      }

      // Add marker to map
      L.marker(latLng)
        .addTo(map)
        .bindPopup(popupContent);
    });

    // Zoom to fit all markers or set default view
    if (bounds.length > 0) {
      map.fitBounds(bounds);
    } else {
      map.setView([11.0, 78.0], 6); // fallback location
    }
  })
  .catch(error => {
    console.error("Error fetching site data:", error);
  });
