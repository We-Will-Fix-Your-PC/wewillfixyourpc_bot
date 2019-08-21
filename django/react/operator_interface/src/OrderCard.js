import React, {Component} from 'react';
import Button from '@material/react-button';
import Dialog, {DialogButton, DialogContent, DialogFooter, DialogTitle} from '@material/react-dialog';
import Radio, {NativeRadioControl} from '@material/react-radio';
import List, {ListItem, ListItemMeta, ListItemText} from '@material/react-list';
import MaterialIcon from "@material/react-material-icon";
import {SockContext} from './App';

import UnlockItem from "./OrderItems/UnlockItem";

class OrderCard extends Component {
    itemsTypes = [{
        type: "unlock",
        name: "Phone unlock",
        component: UnlockItem
    }];

    state = {
        items: [],
        isOpen: false,
        selectedIndex: -1,
        selectedComponent: null
    };

    constructor(props) {
        super(props);

        this.removeItem = this.removeItem.bind(this);
        this.startAddItem = this.startAddItem.bind(this);
        this.addItem = this.addItem.bind(this);
        this.total = this.total.bind(this);
        this.send = this.send.bind(this);
    }

    removeItem(i) {
        const items = this.state.items;
        items.splice(i, 1);
        this.setState({
            items: items
        })
    }

    startAddItem(choice) {
        if (choice === "confirm") {
            if (this.itemsTypes[this.state.selectedIndex]) {
                let type = this.itemsTypes[this.state.selectedIndex];
                this.setState({
                    selectedComponent: type.component
                });
            }
        }
        this.setState({isOpen: false, selectedIndex: -1});
    }

    addItem(title, type, data, price) {
        let items = this.state.items;
        items.push({
            item_type: type,
            item_data: data,
            quantity: 1,
            price: price,
            title: title,
        });
        this.setState({selectedComponent: null, items: items});
    }

    total() {
        return this.state.items.reduce((p, c) => p + (parseFloat(c.price) * c.quantity), 0)
    }

    send() {
        this.props.sock.send(JSON.stringify({
            type: "requestPayment",
            cid: this.props.conversation.id,
            items: this.state.items
        }));
        this.setState({
            items: []
        });
    }

    render() {
        return <div className="OrderCard">
            {this.state.items.length ?
                <List twoLine>
                    {this.state.items.map((item, i) => {
                        return <ListItem key={i}>
                            <ListItemText primaryText={item.title}
                                          secondaryText={`${item.quantity} @ ${item.price} GBP`}/>
                            <ListItemMeta
                                meta={<MaterialIcon icon='remove_circle' onClick={() => this.removeItem(i)}/>}/>
                        </ListItem>
                    })}
                </List> :
                <h4>
                    No items
                </h4>
            }
            <Button onClick={() => this.setState({isOpen: true})}>Add item</Button>
            <div className="summary">
                <div><span>Total:</span> {this.total().toFixed(2)} GBP</div>
                <Button onClick={this.send} disabled={
                    !this.state.items.length || this.props.conversation.agent_responding ||
                    !this.props.conversation.current_user_responding
                }>
                    Send</Button>
            </div>
            <Dialog
                onClose={this.startAddItem}
                open={this.state.isOpen}>
                <DialogTitle>Chose an item to add</DialogTitle>
                <DialogContent>
                    <List singleSelection handleSelect={(selectedIndex) => this.setState({selectedIndex})}>
                        {this.itemsTypes.map((data, i) => {
                            return <ListItem key={i}>
                            <span className='mdc-list-item__graphic'>
                            <Radio>
                              <NativeRadioControl
                                  name='item_type'
                                  value={data.type}
                                  checked={i === this.state.selectedIndex}
                                  onChange={() => {
                                  }}
                              />
                            </Radio>
                          </span>
                                <ListItemText primaryText={data.name}/>
                            </ListItem>
                        })}
                    </List>
                </DialogContent>
                <DialogFooter>
                    <DialogButton action='dismiss'>Cancel</DialogButton>
                    <DialogButton action='confirm' isDefault disabled={!this.itemsTypes[this.state.selectedIndex]}>
                        Ok</DialogButton>
                </DialogFooter>
            </Dialog>
            {this.state.selectedComponent ?
                <this.state.selectedComponent onCancel={() => this.setState({selectedComponent: null})}
                                              onAdd={this.addItem}/> : null}
        </div>
    }
}

export default React.forwardRef((props, ref) =>
    <SockContext.Consumer>
        {value => <OrderCard sock={value} ref={ref} {...props}/>}
    </SockContext.Consumer>
);