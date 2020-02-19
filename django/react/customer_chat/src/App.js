import React, {Component} from 'react';
import './App.scss';
import uuid from 'uuid/v4';
import logo from './wwfypc512.png';
import ReconnectingWebSocket from 'reconnecting-websocket';

const BASE_URL = process.env.NODE_ENV === 'production' ? "https://" + window.location.host + "/" : "http://localhost:8000/";

class MessageData {
    constructor(id, data, app) {
        this.id = id;
        this.data = data;
        this.app = app;
    }

    isLoaded() {
        return this.data !== null;
    }

    load() {
        if (!this.isLoaded()) {
            if (this.app.pending_messages.indexOf(this.id) === -1) {
                this.app.ws.send(JSON.stringify({
                    type: "getMessage",
                    id: this.id
                }));
                this.app.pending_messages.push(this.id);
            }
            return false;
        }
        return true;
    }

    get text() {
        return this.load() ? this.data.text : "";
    }

    get mid() {
        return this.load() ? this.data.mid : null;
    }

    get direction() {
        return this.load() ? this.data.direction : "";
    }

    get timestamp() {
        return this.load() ? this.data.timestamp : 0;
    }

    get image() {
        return this.load() ? this.data.image : null;
    }

    get state() {
        return this.load() ? this.data.state : null;
    }

    get selection() {
        return this.load() ? (this.data.selection ? JSON.parse(this.data.selection) : null) : false;
    }

    get card() {
        return this.load() ? (this.data.card ? JSON.parse(this.data.card) : null) : false;
    }

    get request() {
        return this.load() ? this.data.request: null;
    }

    get sent_by() {
        return this.load() ? this.data.sent_by: null;
    }

    get profile_picture() {
        return this.load() ? this.data.profile_picture_url: null;
    }

    get buttons() {
        return this.load() ? this.data.buttons: null;
    }
}

const status_map = {
    "D": "Delivered",
    "R": "Read",
    "F": "Failed to send",
    "S": "Sending..."
};

class App extends Component {
    constructor(props) {
        super(props);

        this.messages = React.createRef();
        this.nameField = React.createRef();
        this.msgRef = React.createRef();
        this.ws = new ReconnectingWebSocket( process.env.NODE_ENV === 'production' ? "wss://" + window.location.host + "/ws/chat/" : "ws://localhost:8000/ws/chat/");
        this.pending_messages = [];

        this.state = {
            token: null,
            user_profile: null,
            login_url: null,
            logout_url: null,
            error: false,
            loading: true,
            ready: false,
            conversation: null,
            messages: {},
            pending_messages: {}
        };

        this.setupChat = this.setupChat.bind(this);
        this.sendMsg = this.sendMsg.bind(this);
        this.getMsg = this.getMsg.bind(this);
        this.resyncWs = this.resyncWs.bind(this);
        this.wsRecv = this.wsRecv.bind(this);
        this.messageObserverCallback = this.messageObserverCallback.bind(this);

        this.ws.addEventListener('open', this.resyncWs);
        this.ws.addEventListener('close', () => this.setState({}));
        this.ws.addEventListener('message', this.wsRecv);

        this.observer = new IntersectionObserver(this.messageObserverCallback, {
            root: null,
            rootMargin: '0px',
            threshold: 1
        });
    }

    get loading() {
        return this.ws.readyState !== this.ws.OPEN || this.state.loading || !(this.state.ready || !(this.state.conversation && this.state.token));
    }

    resyncWs() {
        this.setState({});
        if (this.state.token) {
            this.ws.send(JSON.stringify({
                type: "resyncReq",
                token: this.state.token
            }));
            this.pending_messages.forEach(m => {
                this.sock.send(JSON.stringify({
                    type: "getMessage",
                    id: m
                }));
            });
        }
    }

    wsRecv(msg) {
        const data = JSON.parse(msg.data);
        if (data.type === "conversation") {
            this.setState({
                conversation: data
            });
        } else if (data.type === "message") {
            const messages = this.state.messages;
            messages[data.id] = new MessageData(data.id, data, this);
            const pending_messages = this.state.pending_messages;
            delete pending_messages[data.mid];
            let p_index = this.pending_messages.indexOf(data.id);
            if (p_index > -1) {
                this.pending_messages.splice(p_index, 1);
            }
            this.setState({
                messages: messages,
                pending_messages: pending_messages
            });
        }
    }

    getMsg(m) {
        if (typeof this.state.messages[m] === "undefined") {
            return new MessageData(m, null, this);
        } else {
            return this.state.messages[m];
        }
    }

    componentDidMount() {
        this.setState({
            loading: true,
            error: false,
            ready: false
        });
        fetch(`${BASE_URL}/chat/config/`, {
            credentials: "include"
        })
            .then(r => {
                if (!r.ok) {
                    throw Error(r.statusText);
                }
                return r
            })
            .then(r => r.json())
            .then(r => {
                this.setState({
                    loading: false,
                    login_url: `${BASE_URL}${r.login_url}?next=${encodeURIComponent(window.location)}`,
                    logout_url: `${BASE_URL}${r.logout_url}?next=${encodeURIComponent(window.location)}`,
                    token: r.token,
                    user_profile: r.profile,
                    ready: !!r.token
                });
                this.resyncWs();
            })
            .catch(err => {
                console.error(err);
                this.setState({
                    error: true,
                    loading: false
                })
            });

        const messages = this.messages.current;
        messages.scrollTo(0, messages.scrollHeight - messages.offsetHeight);
        messages.childNodes.forEach(child => {
            this.observer.observe(child);
        })
    }

    getSnapshotBeforeUpdate(prevProps, prevState) {
        const messages = this.messages.current;
        return {
            scrollTop: messages.scrollTop,
            scrollTopMax: messages.scrollHeight - messages.offsetHeight
        }
    }

    componentDidUpdate(prevProps, prevState, snapshot) {
        const messages = this.messages.current;
        if (snapshot.scrollTop === snapshot.scrollTopMax) {
            messages.scrollTo(0, messages.scrollHeight - messages.offsetHeight);
        }
        messages.childNodes.forEach(child => {
            this.observer.observe(child);
        })
    }

    messageObserverCallback(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const msgId = entry.target.dataset.msgId;
                if (typeof msgId !== "undefined") {
                    const message = this.getMsg(msgId);
                    message.load();
                    this.ws.send(JSON.stringify({
                        type: "readMessage",
                        id: msgId
                    }));
                }
            }
        });
    }

    setupChat() {
        const name = this.nameField.current.value.trim();
        if (!name) {
            return;
        }

        this.setState({
            loading: true,
            error: false,
        });
        const data = new FormData();
        data.append("name", name);
        fetch(`${BASE_URL}/chat/config/`, {
            credentials: "include",
            method: "POST",
            body: data
        })
            .then(r => {
                if (!r.ok) {
                    throw Error(r.statusText);
                }
                return r
            })
            .then(r => r.json())
            .then(r => {
                this.setState({
                    token: r.token,
                    user_profile: {
                        name: name,
                        is_authenticated: false
                    },
                    ready: !!r.token,
                    loading: false
                });
                this.resyncWs();
            })
            .catch(err => {
                console.error(err);
                this.setState({
                    error: true,
                    loading: false
                })
            })
    }

    sendMsg() {
        if (!this.loading) {
            const msg = this.msgRef.current.value.trim();
            const id = uuid();
            const pending_messages = this.state.pending_messages;
            pending_messages[id] = {
                text: msg
            };
            this.setState({
                pending_messages: pending_messages
            });
            this.ws.send(JSON.stringify({
                "type": "sendMessage",
                "content": msg,
                "id": id
            }));
            this.msgRef.current.value = "";
        }
    }

    render() {
        return (
            <div className="App">
                <header>
                    <img src={logo} alt=""/>
                    {this.state.user_profile ? (
                        <div className="name">
                            <h3>Hi, {this.state.user_profile.name}</h3>
                            {this.state.user_profile.is_authenticated ?
                                <span>Not you? <a href={this.state.logout_url}>Logout</a></span>
                                :
                                <span><a href={this.state.login_url}>Login</a> to see your data</span>
                            }
                            {this.state.conversation ? this.state.conversation.current_agent ? <div>
                                You're speaking to {this.state.conversation.current_agent}
                            </div> : null : null }
                        </div>
                    ) : null}
                </header>
                <div className="messages" ref={this.messages}>
                    {this.state.conversation ? this.state.conversation.messages.map((id, i) => {
                            let msg = this.getMsg(id);
                            const next_mid = this.state.conversation.messages[i+1];
                            let next_msg = (typeof next_mid !== 'undefined') ? this.getMsg(next_mid) : null;

                            if (msg.isLoaded()) {
                                return <div className={`dir-${msg.direction}`} data-msg-id={msg.id} key={msg.id}>
                                    <div>
                                        {msg.profile_picture ? <img src={msg.profile_picture} alt=""/> : (
                                            msg.direction === "I" ? <img src={logo} alt=""/> : null
                                        )}
                                        <div>
                                            {msg.text ? <span
                                                dangerouslySetInnerHTML={{__html: msg.text.replace(/\n/g, "<br />")}}/> : null}
                                            {msg.request === "sign_in" ? (
                                                !this.state.user_profile.is_authenticated ?
                                                    <a href={this.state.login_url} className="btn">Sign in</a> :
                                                    <button disabled={true}>Sign in complete</button>
                                            ) : null}
                                            {msg.buttons.map(b => {
                                                if (b.type === "url") {
                                                    return <a href={b.url}>{b.text}</a>
                                                }
                                            })}
                                        </div>
                                    </div>
                                    {msg.sent_by && !(next_msg && next_msg.isLoaded() && next_msg.sent_by === msg.sent_by) ?
                                        <span>Sent by {msg.sent_by}</span> : null}
                                    {msg.direction === "O" && msg.state && !(next_msg && next_msg.isLoaded() && next_msg.state === msg.state) ?
                                        <span>{status_map[msg.state]}</span> : null
                                    }
                                </div>
                            } else {
                                return <div data-msg-id={msg.id} key={msg.id}>
                                    <div>
                                        <div>Loading...</div>
                                    </div>
                                </div>
                            }
                        }) : null }
                    {Object.values(this.state.pending_messages).map((m, i) => {
                        return <div key={i} className="dir-O">
                            <div>
                                <div>
                                    <span>{m.text}</span>
                                </div>
                            </div>
                            <span>Sending...</span>
                        </div>
                    })}
                </div>
                <div className="message-input">
                    <textarea wrap="soft" placeholder="Your message..." ref={this.msgRef}/>
                    <i className="material-icons" onClick={this.sendMsg}>send</i>
                </div>
                {this.loading ? (
                    <div className="dialog name-dialog">
                        <div className="dialog-content">
                            <span>
                                <h1>Loading...</h1>
                            </span>
                        </div>
                    </div>
                ) : (
                    this.state.error ? (
                        <div className="dialog name-dialog">
                            <div className="dialog-content">
                                <h1>There was an error</h1>
                                <div>
                                    Please refresh the page
                                </div>
                            </div>
                        </div>
                    ) : (
                        !this.state.ready ? (
                            <div className="dialog name-dialog">
                                <div className="dialog-content">
                                    <h1>Let's get you some help</h1>
                                    <div>
                                        <label htmlFor="#name-field">What's your name?</label>
                                        <input type="text" id="name-field" ref={this.nameField}/>
                                        <button onClick={this.setupChat}>Submit</button>
                                        <h2>Or</h2>
                                        <a href={this.state.login_url} className="btn">Login</a>
                                    </div>
                                </div>
                            </div>
                        ) : null
                    )
                )}
            </div>
        );
    }
}

export default App;
