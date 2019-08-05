import React, {Component} from 'react';
import TextField, {Input} from '@material/react-text-field';
import dateformat from 'dateformat';

import MaterialIcon from '@material/react-material-icon';
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

    render() {
        return (
            <div className='conversation'>
                <div className="messages" ref="messages">
                    {this.props.messages.map((m, i, a) => {
                        let d = new Date(0);
                        d.setUTCSeconds(m.timestamp);

                        let out = [];

                        if (i !== 0) {
                            let prevDate = new Date(0);
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
                                <div dangerouslySetInnerHTML={{__html: m.text.replace(/\n/g, "<br />")}}/>
                                <span>{dateformat(d, "h:MM TT")}</span>
                            </div>
                        </div>);

                        return out
                    })}
                </div>
                <TextField
                    fullWidth
                    outlined
                    onTrailingIconSelect={() => {
                        this.setState({value: ""});
                        this.props.onSend(this.state.value);
                    }}
                    trailingIcon={<MaterialIcon role="button" icon="send"/>}
                ><Input
                    value={this.state.value}
                    onChange={(e) => this.setState({value: e.currentTarget.value})}/>
                </TextField>
            </div>
        );
    }
}
