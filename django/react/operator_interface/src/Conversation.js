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
        }
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
    }

    componentDidMount() {
        const messages = this.refs.messages;
        messages.scrollTo(0, messages.scrollHeight - messages.offsetHeight);
    }

    render() {
        return (
            <div className='conversation'>
                <div className="main">
                    <div className="messages" ref="messages">
                        {this.props.conversation.messages.map((m, i, a) => {
                            let d = new Date(0);
                            d.setUTCSeconds(m.timestamp);

                            let out = [];
                            let prevDate = new Date(0);

                            if (i !== 0) {
                                prevDate.setUTCSeconds(a[i - 1].timestamp);
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

                            out.push(<div key={i * 2}>
                                <div className={"dir-" + m.direction}>
                                    {m.text ?
                                        <div dangerouslySetInnerHTML={{__html: m.text.replace(/\n/g, "<br />")}}/> : (
                                            m.image ? <img src={m.image} alt=""/> : null
                                        )}
                                    {m.payment_request ?
                                        <span>Payment request for: {m.payment_request}</span> : null
                                    }
                                    {m.payment_confirm ?
                                        <span>Payment receipt for: {m.payment_confirm}</span> : null
                                    }
                                    <span>{dateformat(d, "h:MM TT")}</span>
                                    {m.direction === "I" ? <span>{m.read ? "Read" : "Delivered"}</span> : null}
                                </div>
                            </div>);

                            return out
                        })}
                    </div>
                    <TextField
                        fullWidth
                        outlined
                        onTrailingIconSelect={() => {
                            if (this.state.value.length && !this.props.conversation.agent_responding) {
                                this.props.onSend(this.state.value);
                                this.setState({value: ""});
                            }
                        }}
                        trailingIcon={<MaterialIcon role="button" icon="send"/>}
                    ><Input
                        value={this.state.value}
                        disabled={this.props.conversation.agent_responding ||
                        !this.props.conversation.current_user_responding}
                        onChange={(e) => this.setState({value: e.currentTarget.value})}/>
                    </TextField>
                </div>
                <div className="panel">
                    <CustomerPanel conversation={this.props.conversation}/>
                </div>
            </div>
        );
    }
}
