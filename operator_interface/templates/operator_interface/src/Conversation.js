import React, {Component} from 'react';
import TextField, {HelperText, Input} from '@material/react-text-field';

import MaterialIcon from '@material/react-material-icon';
import './App.scss';

export default class Conversation extends Component {
    constructor(props) {
        super(props);

        this.state = {
            value: "",
        }
    }

    render() {
        return (
            <div className='conversation'>
                <div className="messages">
                    {this.props.messages.map((m, i) => (
                        <div key={i}>
                            <div className={"dir-" + m.direction}
                                 dangerouslySetInnerHTML={{__html: m.text.replace(/\n/g, "<br />")}} />
                        </div>
                    ))}
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
