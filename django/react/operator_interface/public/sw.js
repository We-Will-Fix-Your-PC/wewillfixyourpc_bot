self.addEventListener('push', function (event) {
    console.log('[Service Worker] Push Received.');
    console.log(`[Service Worker] Push had this data: "${event.data.text()}"`);

    const data = event.data.json();
    if (data.type === "alert") {
        event.waitUntil(self.registration.showNotification("We Will Fix Your PC", {
            body: `${data.name} - ${data.text}`
        }));
    } else if (data.type === "message") {
        event.waitUntil(self.registration.showNotification("New message", {
            body: `${data.name} - ${data.text}`
        }));
    }
});

self.addEventListener('notificationclick', function (event) {
    console.log('[Service Worker] Notification click Received.');

    event.notification.close();

    event.waitUntil(clients.matchAll({
        type: "window"
    }).then(function (clientList) {
        for (let i = 0; i < clientList.length; i++) {
            const client = clientList[i];
            if (client.url === '/' && 'focus' in client)
                return client.focus();
        }
        if (clients.openWindow)
            return clients.openWindow('/');
    }));
});
