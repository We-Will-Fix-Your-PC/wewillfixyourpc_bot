import React from 'react';
import ReactDOM from 'react-dom';
import './index.css';
import App from './App';

const applicationServerPublicKey = 'BD9YFnVo9uQ1QQNcAV__0luLgROO_4cGRCNh4KRZaxeVwW4m21ApNxUuQFIwiNFk4XBYF7r0i9LOxHbxoP1U4zI';

function urlB64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/-/g, '+')
        .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

ReactDOM.render(<App/>, document.getElementById('root'));

if ('serviceWorker' in navigator && 'PushManager' in window) {
    navigator.serviceWorker.register('sw.js')
        .then(function (swReg) {
            console.log('Service Worker is registered', swReg);

            swReg.pushManager.getSubscription()
                .then(function (subscription) {
                    const isSubscribed = !(subscription === null);

                    if (isSubscribed) {
                        console.log('User IS subscribed.');
                    } else {
                        console.log('User is NOT subscribed.');

                        const applicationServerKey = urlB64ToUint8Array(applicationServerPublicKey);
                        setTimeout(() => {
                            swReg.pushManager.subscribe({
                                userVisibleOnly: true,
                                applicationServerKey: applicationServerKey
                            })
                                .then(function (subscription) {
                                    console.log('User is subscribed.');

                                    fetch(process.env.NODE_ENV === 'production' ? "/push_subscription/" :
                                        "http://localhost:8000/push_subscription/", {
                                        credentials: 'include',
                                        method: "POST",
                                        body: JSON.stringify({
                                            subscription_info: subscription
                                        })
                                    })
                                        .then(resp => resp.json())
                                        .then(data => {
                                            window.localStorage.setItem("subscription_id", data.id)
                                        })
                                        .catch(e => {
                                            console.error(e);
                                        });
                                })
                                .catch(function (err) {
                                    console.log('Failed to subscribe the user: ', err);
                                    if (Notification.permission === 'denied') {
                                        console.warn("Push Messaging Blocked");

                                        const subscription_id = window.localStorage.getItem("subscription_id");
                                        if (subscription_id !== null) {
                                            fetch((process.env.NODE_ENV === 'production' ? "/push_subscription/" :
                                                "http://localhost:8000/push_subscription/")
                                                + `?subscription_id=${subscription_id}`, {
                                                credentials: 'include',
                                                method: "DELETE",
                                            })
                                                .then(resp => resp.json())
                                                .then(data => {
                                                    window.localStorage.setItem("subscription_id", data.id)
                                                })
                                                .catch(e => {
                                                    console.error(e);
                                                });
                                        }
                                    }
                                });
                        }, 1000);

                    }
                });
        })
        .catch(function (error) {
            console.error('Service Worker Error', error);
        });
} else {
    console.warn('Push messaging is not supported');
}

