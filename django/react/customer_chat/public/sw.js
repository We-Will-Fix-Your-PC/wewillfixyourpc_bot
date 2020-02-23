const urlToOpen = new URL("/chat/", self.location.origin).href;

self.addEventListener('push', function (event) {
    if (event.data) {
        const data = event.data.json();
        if (data.type === "message") {
            const isFocused = clients.matchAll({
                type: 'window',
                includeUncontrolled: true
            }).then((windowClients) => {
                let clientIsFocused = false;

                for (let i = 0; i < windowClients.length; i++) {
                    const windowClient = windowClients[i];
                    if (windowClient.focused && windowClient.url === urlToOpen) {
                        clientIsFocused = true;
                        break;
                    }
                }

                return clientIsFocused;
            });
            const promiseChain = isFocused.then(f => {
                if (f) {
                    return;
                }
                return self.registration.showNotification("New message from We Will Fix Your PC", {
                    body: data.contents,
                    timestamp: data.timestamp * 1000
                })
            });

            event.waitUntil(promiseChain);
        }
    }
});

self.addEventListener('notificationclick', function (event) {
    const clickedNotification = event.notification;
    clickedNotification.close();

    const promiseChain = clients.matchAll({
        type: 'window',
        includeUncontrolled: true
    }).then((windowClients) => {
        let matchingClient = null;

        for (let i = 0; i < windowClients.length; i++) {
            const windowClient = windowClients[i];
            if (windowClient.url === urlToOpen) {
                matchingClient = windowClient;
                break;
            }
        }

        if (matchingClient) {
            return matchingClient.focus();
        } else {
            return clients.openWindow(urlToOpen);
        }
    });

    event.waitUntil(promiseChain);
});
