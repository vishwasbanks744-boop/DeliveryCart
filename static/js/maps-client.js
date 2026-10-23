(function() {
    let configPromise;
    let mapsScriptPromise;
    const renderedMaps = new WeakMap();

    function clientConfig() {
        if (!configPromise) {
            configPromise = fetch("/api/config/public", { credentials: "same-origin" })
                .then(function(response) {
                    if (!response.ok) throw new Error("Could not load Maps configuration.");
                    return response.json();
                });
        }
        return configPromise;
    }

    function loadGoogleMaps(libraries) {
        return clientConfig().then(function(config) {
            if (!config.googleMapsApiKey) {
                throw new Error("Google Maps is not configured on this server.");
            }
            if (!mapsScriptPromise) {
                mapsScriptPromise = new Promise(function(resolve, reject) {
                    if (window.google && window.google.maps && window.google.maps.importLibrary) {
                        resolve();
                        return;
                    }
                    const script = document.createElement("script");
                    const params = new URLSearchParams({
                        key: config.googleMapsApiKey,
                        v: "weekly",
                        loading: "async",
                        callback: "__ramjicartMapsLoaded"
                    });
                    if (config.googleMapsMapId) params.set("map_ids", config.googleMapsMapId);
                    script.src = "https://maps.googleapis.com/maps/api/js?" + params.toString();
                    script.async = true;
                    let settled = false;
                    const timeout = window.setTimeout(function() {
                        if (settled) return;
                        settled = true;
                        delete window.__ramjicartMapsLoaded;
                        mapsScriptPromise = null;
                        reject(new Error("Google Maps did not finish loading. Check the key and enabled APIs."));
                    }, 20000);
                    window.__ramjicartMapsLoaded = function() {
                        if (settled) return;
                        settled = true;
                        window.clearTimeout(timeout);
                        delete window.__ramjicartMapsLoaded;
                        resolve();
                    };
                    script.onerror = function() {
                        if (settled) return;
                        settled = true;
                        window.clearTimeout(timeout);
                        delete window.__ramjicartMapsLoaded;
                        mapsScriptPromise = null;
                        reject(new Error("Google Maps could not be loaded. Check the key and enabled APIs."));
                    };
                    document.head.appendChild(script);
                });
            }
            return mapsScriptPromise.then(function() {
                return Promise.all((libraries || ["maps", "marker"]).map(function(library) {
                    return window.google.maps.importLibrary(library);
                })).then(function(imports) {
                    return { config: config, imports: imports };
                });
            });
        });
    }

    async function renderMap(container, points) {
        const validPoints = (points || []).filter(function(point) {
            return point && Number.isFinite(Number(point.latitude))
                && Number.isFinite(Number(point.longitude));
        });
        if (!container || !validPoints.length) return null;
        const loaded = await loadGoogleMaps(["maps", "marker"]);
        const MapClass = loaded.imports[0].Map;
        const AdvancedMarkerElement = loaded.imports[1].AdvancedMarkerElement;
        const mapId = loaded.config.googleMapsMapId || "DEMO_MAP_ID";
        let state = renderedMaps.get(container);
        const bounds = new google.maps.LatLngBounds();
        validPoints.forEach(function(point) {
            bounds.extend({ lat: Number(point.latitude), lng: Number(point.longitude) });
        });
        if (!state) {
            state = {
                map: new MapClass(container, {
                    center: bounds.getCenter(),
                    zoom: validPoints.length > 1 ? 12 : 15,
                    mapId: mapId,
                    streetViewControl: false,
                    mapTypeControl: false,
                    fullscreenControl: true
                }),
                markers: []
            };
            renderedMaps.set(container, state);
        }
        state.markers.forEach(function(marker) { marker.map = null; });
        state.markers = validPoints.map(function(point) {
            return new AdvancedMarkerElement({
                map: state.map,
                position: { lat: Number(point.latitude), lng: Number(point.longitude) },
                title: String(point.title || "Location")
            });
        });
        if (validPoints.length > 1) state.map.fitBounds(bounds);
        else {
            state.map.setCenter(bounds.getCenter());
            state.map.setZoom(15);
        }
        return state.map;
    }

    function searchUrl(query) {
        return "https://www.google.com/maps/search/?api=1&query="
            + encodeURIComponent(String(query || "").trim());
    }

    function directionsUrl(origin, destination) {
        const params = new URLSearchParams({
            api: "1",
            origin: String(origin || "").trim(),
            destination: String(destination || "").trim()
        });
        return "https://www.google.com/maps/dir/?" + params.toString();
    }

    function getCurrentPosition(options) {
        return new Promise(function(resolve, reject) {
            if (!navigator.geolocation) {
                reject(new Error("This browser does not support device location."));
                return;
            }
            navigator.geolocation.getCurrentPosition(resolve, reject, options);
        });
    }

    function watchPosition(success, error, options) {
        if (!navigator.geolocation) {
            throw new Error("Location sharing is not supported by this browser.");
        }
        return navigator.geolocation.watchPosition(success, error, options);
    }

    function clearWatch(watchId) {
        if (navigator.geolocation) {
            navigator.geolocation.clearWatch(watchId);
        }
    }

    window.RamjicartMaps = Object.freeze({
        loadGoogleMaps: loadGoogleMaps,
        renderMap: renderMap,
        searchUrl: searchUrl,
        directionsUrl: directionsUrl,
        getCurrentPosition: getCurrentPosition,
        watchPosition: watchPosition,
        clearWatch: clearWatch
    });
})();
