import React, {Component} from 'react';
import TextField, {Input} from '@material/react-text-field';
import dateformat from 'dateformat';

import MaterialIcon from '@material/react-material-icon';
import CustomerPanel from "./CustomerPanel";
import './App.scss';
import Dialog, {DialogButton, DialogContent, DialogFooter, DialogTitle} from "@material/react-dialog";

export const entity_map = {
    "phone-number": "phone number",
    "email": "email",
    "first-name": "first name",
    "last-name": "first name",
};

export const request_map = {
    "sign_in": "login",
    "confirmation": "confirmation",
    "phone": "phone number",
    "time": "date and time",
};

const status_map = {
    "D": "Delivered",
    "R": "Read",
    "F": "Failed to send",
    "S": "Sending..."
};

export const a_or_an = (word) => {
    const vowelRegex = '^[aieouAIEOU].*';
    if (word.match(vowelRegex)) {
        return `An ${word}`;
    } else {
        return `A ${word}`;
    }
};

export default class Conversation extends Component {
    constructor(props) {
        super(props);

        this.state = {
            value: "",
            isOpen: false,
            entity: null,
        };

        this.messageObserverCallback = this.messageObserverCallback.bind(this);
        this.openEntityDialog = this.openEntityDialog.bind(this);
        this.updateEntity = this.updateEntity.bind(this);

        this.observer = new IntersectionObserver(this.messageObserverCallback, {
            root: null,
            rootMargin: '0px',
            threshold: 1
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

    openEntityDialog(entity) {
        this.setState({isOpen: true, entity: entity});
    }

    updateEntity(choice) {
        if (choice === "confirm") {
            this.props.conversation.save_entity(this.state.entity);
        }
        this.setState({isOpen: false});
    }

    render() {
        return (
            <div className='conversation'>
                <div className="main">
                    <Dialog
                        onClose={this.updateEntity}
                        open={this.state.isOpen}>
                        {this.state.isOpen ? <React.Fragment>
                            <DialogTitle>Save the {entity_map[this.state.entity.entity]} to customer?</DialogTitle>
                            <DialogContent>
                                The customer's {entity_map[this.state.entity.entity]} will be set
                                to {this.state.entity.text_value}
                                <br/>
                                <b>
                                    Note: please be certain this is the legitimate data of the customer, the system may
                                    also request further authentication from the customer automatically
                                </b>
                            </DialogContent>
                            <DialogFooter>
                                <DialogButton action='dismiss'>Cancel</DialogButton>
                                <DialogButton action='confirm' isDefault>Ok</DialogButton>
                            </DialogFooter>
                        </React.Fragment> : null}
                    </Dialog>
                    <div className="messages" ref="messages">
                        {this.props.conversation.messages.map((m, i, a) => {
                            let out = [];
                            let d = new Date(0);
                            let prevDate = new Date(0);

                            if (m.isLoaded()) {
                                d.setUTCSeconds(m.timestamp);
                                let cur_platform = m.platform;
                                let last_platform = null;

                                if (i !== 0) {
                                    if (a[i - 1].isLoaded()) {
                                        prevDate.setUTCSeconds(a[i - 1].timestamp);
                                        last_platform = a[i - 1].platform;
                                    }
                                    if (!(prevDate.getDay() === d.getDay() && prevDate.getMonth() === d.getMonth() &&
                                        prevDate.getFullYear() === d.getFullYear())) {
                                        out.push(<div key={(i * 3) + 1}>
                                            <span>
                                                <span>{dateformat(d, "ddd mmm dS yyyy")}</span>
                                            </span>
                                        </div>)
                                    }
                                    if (cur_platform !== last_platform) {
                                        out.push(<div key={(i * 3) + 2}>
                                            <span>
                                                <span>{m.platform_name}</span>
                                            </span>
                                        </div>)
                                    }
                                } else {
                                    out.push(<div key={(i * 3) + 2}>
                                        <span>
                                            <span>{m.platform_name}</span>
                                        </span>
                                    </div>);
                                    out.push(<div key={(i * 3) + 1}>
                                        <span>
                                            <span>{dateformat(d, "ddd mmm dS yyyy")}</span>
                                        </span>
                                    </div>);
                                }
                            }

                            out.push(<div key={i * 3} data-msg-id={m.id}>
                                {m.isLoaded() ? m.end ?
                                    <span>
                                        <span>Session end</span>
                                    </span>
                                    :
                                    <div className={"dir-" + m.direction}>
                                        {m.text ?
                                            <div
                                                dangerouslySetInnerHTML={{__html: m.text.replace(/\n/g, "<br />")}}/> : (
                                                m.image ? <img src={m.image} alt=""/> : null
                                            )}
                                        {m.entities
                                            .filter(e => typeof entity_map[e.entity] !== "undefined")
                                            .map((entity, i) => (
                                                <span className="entity" key={i} onClick={() => this.openEntityDialog(entity)}>
                                                    {a_or_an(entity_map[entity.entity])} was detected. Click here to save it.
                                                </span>
                                            ))
                                        }
                                        {m.request ?
                                            <span>Request for {request_map[m.request]}</span> : null
                                        }
                                        {m.payment_request ?
                                            <span>Payment request for: {m.payment_request.id}</span> : null
                                        }
                                        {m.payment_confirm ?
                                            <span>Payment receipt for: {m.payment_confirm.id}</span> : null
                                        }
                                        {m.selection ?
                                            <div>
                                                Selection:
                                                <h3>{m.selection.title}</h3>
                                                <ul>
                                                    {m.selection.items.map((item, i) => (
                                                        <li key={i}>{item.title}</li>
                                                    ))}
                                                </ul>
                                            </div> : null
                                        }
                                        <span>{dateformat(d, "h:MM TT")}</span>
                                        {m.sent_by ?
                                            <span>Sent by {m.sent_by}</span> : null
                                        }
                                        {m.direction === "I" && m.state ?
                                            <span>{status_map[m.state]}</span> : null
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
                                if (this.state.value.length && this.props.conversation.can_message()) {
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
