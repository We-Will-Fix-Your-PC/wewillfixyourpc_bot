import React, {Component} from 'react';
import TopAppBar, {
    TopAppBarFixedAdjust,
    TopAppBarRow,
    TopAppBarTitle,
    TopAppBarSection,
    TopAppBarIcon
} from '@material/react-top-app-bar';
import Drawer, {
    DrawerAppContent,
    DrawerContent,
    DrawerHeader,
    DrawerTitle,
    DrawerSubtitle
} from '@material/react-drawer';
import MaterialIcon from '@material/react-material-icon';
import List, {ListItem, ListItemGraphic, ListItemText} from '@material/react-list';
import ReconnectingWebSocket from './reconnecting-websocket';
import Conversation from './Conversation';

import './App.scss';

class App extends Component {
    constructor(props) {
        super(props);

        this.state = {
            open: true,
            lastMessage: 0,
            selectedIndex: null,
            conversations: [],
            conversationMap: {}
        };

        this.selectConversation = this.selectConversation.bind(this);
        this.handleOpen = this.handleOpen.bind(this);
        this.handleReceiveMessage = this.handleReceiveMessage.bind(this);
        this.onSend = this.onSend.bind(this);
    }

    componentDidMount() {
        fetch("http://localhost:8000/token/", {
            credentials: 'include'
        })
            .then(resp => resp.text())
            .then(resp => {
                this.sock = new ReconnectingWebSocket("wss://" + window.location.host + "/websocket/", resp, {automaticOpen: false});
                this.sock.onopen = this.handleOpen;
                this.sock.onmessage = this.handleReceiveMessage;
                this.sock.open();
            })
            .catch((e) => {
                console.error(e);
                window.location.reload();
            });
    }

    componentWillUnmount() {
        this.sock.close();
    }

    selectConversation(i) {
        this.setState({
            selectedIndex: i
        })
    }

    handleReceiveMessage(msg) {
        const data = JSON.parse(msg.data);

        const message = {
            id: data.id,
            direction: data.direction,
            timestamp: data.timestamp,
            text: data.text,
        };
        const conversations = this.state.conversations;
        const conversationMap = this.state.conversationMap;
        let conversationId = conversationMap[data.conversation.id];
        if (typeof conversationId === "undefined") {
            conversationId = conversations.push({
                id: data.conversation.id,
                customer_name: data.conversation.customer_name,
                username: data.conversation.customer_username,
                picture: data.conversation.customer_pic,
                messages: [message]
            }) - 1;
            conversationMap[data.conversation.id] = conversationId;
        } else {
            conversations[conversationId].customer_name = data.conversation.customer_name;
            conversations[conversationId].username = data.conversation.customer_username;
            conversations[conversationId].picture = data.conversation.customer_pic;
        }
        conversations[conversationId].messages.push(message);
        this.setState({
            conversations: conversations,
            conversationMap: conversationMap,
            lastMessage: message.timestamp,
        });
    }

    handleOpen() {
        this.sock.send(JSON.stringify({
            "type": "resyncReq",
            "lastMessage": this.state.lastMessage
        }));
    }

    onSend(text) {
        this.sock.send(JSON.stringify({
            "type": "msg",
            "text": text,
            "cid": this.state.conversations[this.state.selectedIndex].id
        }));
    }

    render() {
        return (
            <div className='drawer-container'>
                <Drawer dismissible open={this.state.open}>
                    <DrawerHeader>
                        <DrawerTitle tag='h2'>
                            Operator interface
                        </DrawerTitle>
                        <DrawerSubtitle>
                            Q Misell
                        </DrawerSubtitle>
                    </DrawerHeader>

                    <DrawerContent>
                        <List twoLine avatarList singleSelection selectedIndex={this.state.selectedIndex}>
                            {this.state.conversations.map((c, i) => (
                                <ListItem key={i} onClick={() => this.selectConversation(i)}>
                                    <ListItemGraphic graphic={<img src={c.picture} alt=""/>}/>
                                    <ListItemText
                                        primaryText={c.customer_name}
                                        secondaryText='Jan 9, 2018'/>
                                </ListItem>
                            ))}
                        </List>
                    </DrawerContent>
                </Drawer>

                <DrawerAppContent className='drawer-app-content'>
                    <TopAppBar>
                        <TopAppBarRow>
                            <TopAppBarSection align='start'>
                                <TopAppBarIcon navIcon>
                                    <MaterialIcon icon='menu' onClick={() => this.setState({open: !this.state.open})}/>
                                </TopAppBarIcon>
                                <TopAppBarTitle>{this.state.selectedIndex === null ? "Loading..." :
                                    this.state.conversations[this.state.selectedIndex].customer_name +
                                    ((this.state.conversations[this.state.selectedIndex].username != null) ? " - " +
                                    this.state.conversations[this.state.selectedIndex].username : "")}</TopAppBarTitle>
                            </TopAppBarSection>
                        </TopAppBarRow>
                    </TopAppBar>

                    <TopAppBarFixedAdjust>
                        {this.state.selectedIndex === null ?
                            <h2>Please select a conversation from the drawer</h2> :
                            <Conversation
                                messages={this.state.conversations[this.state.selectedIndex].messages}
                                onSend={this.onSend}
                            />}
                    </TopAppBarFixedAdjust>
                </DrawerAppContent>
            </div>
        );
    }
}

export default App;
