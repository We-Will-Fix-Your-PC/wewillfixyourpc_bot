import React, {Component} from 'react';
import TextField, {Input} from '@material/react-text-field';
import dateformat from 'dateformat';

import MaterialIcon from '@material/react-material-icon';
import CustomerPanel from "./CustomerPanel";
import './App.scss';

export default class Conversation extends Component {
    constructor(props) {
        super(props);

        this.state = {
            value: "",
        };

        this.messageObserverCallback = this.messageObserverCallback.bind(this);

        this.observer = new IntersectionObserver(this.messageObserverCallback, {
            root: null,
            rootMargin: '0px',
            threshold: 0
        });
    }

    getSnapshotBeforeUpdate(prevProps, prevState) {
        const messages = this.refs.messages;
        return {
            scrollTop: messages.scrollTop,
            scrollTopMax: messages.scrollHeight - messages.offsetHeight
        }
    }

    componentDidUpdate(prevProps, prevState, snapshot) {
        const messages = this.refs.messages;
        if (snapshot.scrollTop === snapshot.scrollTopMax) {
            messages.scrollTo(0, messages.scrollHeight - messages.offsetHeight);
        }
        messages.childNodes.forEach(child => {
            this.observer.observe(child);
        })
    }

    componentDidMount() {
        const messages = this.refs.messages;
        messages.scrollTo(0, messages.scrollHeight - messages.offsetHeight);
        messages.childNodes.forEach(child => {
            this.observer.observe(child);
        })
    }

    messageObserverCallback(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const msgId = entry.target.dataset.msgId;
                if (typeof msgId !== "undefined") {
                    const message = this.props.conversation.get_message(msgId);
                    message.load();
                }
            }
        });
    }

    render() {
        return (
            <div className='conversation'>
                <div className="main">
                    <div className="messages" ref="messages">
                        {this.props.conversation.messages.map((m, i, a) => {
                            let out = [];
                            let d = new Date(0);
                            let prevDate = new Date(0);

                            if (m.isLoaded()) {
                                d.setUTCSeconds(m.timestamp);


                                if (i !== 0) {
                                    if (a[i - 1].isLoaded()) {
                                        prevDate.setUTCSeconds(a[i - 1].timestamp);
                                    }
                                    if (!(prevDate.getDay() === d.getDay() && prevDate.getMonth() === d.getMonth() &&
                                        prevDate.getFullYear() === d.getFullYear())) {
                                        out.push(<div key={(i * 2) + 1}>
                                            <span>
                                                <span>{dateformat(d, "ddd mmm dS yyyy")}</span>
                                            </span>
                                        </div>)
                                    }
                                } else {
                                    out.push(<div key={(i * 2) + 1}>
                                        <span>
                                            <span>{dateformat(d, "ddd mmm dS yyyy")}</span>
                                        </span>
                                    </div>);
                                }
                            }

                            out.push(<div key={i * 2} data-msg-id={m.id}>
                                {m.isLoaded() ?
                                    <div className={"dir-" + m.direction}>
                                        {m.text ?
                                            <div
                                                dangerouslySetInnerHTML={{__html: m.text.replace(/\n/g, "<br />")}}/> : (
                                                m.image ? <img src={m.image} alt=""/> : null
                                            )}
                                        {m.payment_request ?
                                            <span>Payment request for: {m.payment_request.id}</span> : null
                                        }
                                        {m.payment_confirm ?
                                            <span>Payment receipt for: {m.payment_confirm.id}</span> : null
                                        }
                                        <span>{dateformat(d, "h:MM TT")}</span>
                                        {m.direction === "I" && m.delivered ?
                                            <span>{m.read ? "Read" : "Delivered"}</span> : null
                                        }
                                    </div> : <div className="dir-O">
                                        <div>Loading...</div>
                                    </div>
                                }
                            </div>);

                            return out
                        })}
                    </div>
                    {this.props.conversation.can_interact() ?
                        <TextField
                            fullWidth
                            outlined
                            onTrailingIconSelect={() => {
                                if (this.state.value.length && !this.props.conversation.can_message()) {
                                    this.props.conversation.send(this.state.value);
                                    this.setState({value: ""});
                                }
                            }}
                            trailingIcon={<MaterialIcon role="button" icon="send"/>}
                        >

                            <Input
                                value={this.state.value}
                                disabled={!this.props.conversation.can_message()}
                                onChange={(e) => this.setState({value: e.currentTarget.value})}
                            />
                        </TextField>
                        :
                        <div className="no-replies">Sender doesnt support replies</div>
                    }
                </div>
                <div className="panel">
                    <CustomerPanel conversation={this.props.conversation}/>
                </div>
            </div>
        );
    }
}
