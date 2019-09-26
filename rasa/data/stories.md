## price reaction
* opinion+negative{"price": "expensive"}
  - utter_good_value
  - utter_ask_continue

## general bad reaction
* opinion+negative
  - utter_ask_continue

## simple acknowledgement
* opinion+positive OR acknowledge
  - utter_positive_feedback_reaction

## cheer up
* mood_unhappy
  - cat_pic

## next question no
> anything_else
    - utter_anything_else
* deny
> end
 
## next question ys
> anything_else
    - utter_anything_else
* affirm
    - utter_can_do

## anything else unlock
> anything_else
   - utter_anything_else
* unlock
    - unlock_lookup_form
    - unlock_lookup
    - update_info_slots
> unlockable

## anything else repair
> anything_else
   - utter_anything_else
* repair
    - repair_form
    - form{"name": "repair_form"}
    - form{"name": null}
    - repair
> repairable

## end
* end
> end

## end - slow
> end
  - slot{"instant_response_required": false}
  - utter_goodbye
> rate

## end - fast
> end
  - slot{"instant_response_required": true}
  - utter_restart
    
## rate
> rate
* rate
    - rate_slot
    - rate_form
    - form{"name": "rate_form"}
    - form{"name": null}
    - utter_thanks_end
    - action_restart
    
## cant help - yes
> cant_help    
  - utter_cant_help
* affirm
> need_help
    
## cant help - no
> cant_help    
  - utter_cant_help
* deny
  - utter_can_do
    
## Out of scope
* out_of_scope
> cant_help

## sign in error
* sign_in_error
  - utter_sign_in_error
> anything_else

## sign in cancelled
* sign_in_cancelled
> anything_else
  
## request_human
* request_human OR stop
> need_help

## need help 
> need_help
    - request_human
  
## ask mood
* ask_mood
  - utter_mood
  
## ask weather
* ask_weather
  - utter_weather
  
## ask history
* ask_history
  - utter_history
  
## ask what's possible
* ask_whatspossible
  - utter_explain_whatspossible

## opening hours
* support_opening_hours
    - support_opening_hours
> anything_else

## contact
* support_contact
    - support_contact
> anything_else

## email
* support_contact_email
    - support_contact_email
> anything_else

## phone
* support_contact_phone
    - support_contact_phone
> anything_else

## location
* support_location
    - support_location
> anything_else

## woodchuck
* easteregg_woodchuck
    - utter_woodchuck
    
## fox sounds
* easteregg_fox_sounds
    - utter_fox_sounds

## meaning of life
* easteregg_meaning_of_life
    - utter_meaning_of_life
    
## chicken cross road
* easteregg_why_chicken_cross_road
    - utter_why_chicken_cross_road

## interactive_story
* support_contact_email
    - support_contact_email
    - utter_anything_else
* out_of_scope
> cant_help

## repair
* repair
    - repair_form
    - form{"name": "repair_form"}
    - form{"name": null}
    - repair
> repairable

## repairable
> repairable
    - slot{"repairable": false}
    - utter_ask_book
* deny
> anything_else

## repairable
> repairable
    - slot{"repairable": false}
    - utter_ask_book
* affirm
> repair_book

## repair - sign in
> repair_book
    - slot{"sign_in_supported": true}
    - sign_in
> repair_sign_in

## repair - sign in success
> repair_sign_in
* sign_in
> repair_book_2

## repair - sign in error
> repair_sign_in
* sign_in_error
  - utter_sign_in_error
> anything_else

## repair - sign in cancel
> repair_sign_in
* sign_in_cancelled
> anything_else

## repair - no sign in
> repair_book
    - slot{"sign_in_supported": false}
> repair_book_2

## actually book repair
> repair_book_2
    - repair_book_check
> repair_book_3

## actually book repair loop
> repair_book_3
    - slot{"repairable": false}
* resolve_entity OR device_model
    - repair_book_clarify
> repair_book_3

## actually book repair loop break
> repair_book_3
   - slot{"repairable": true}
   - repair_book_form
> anything_else

## not repairable
> repairable
    - slot{"repairable": false}
> anything_else

## unlock
* unlock
    - unlock_lookup_form
    - unlock_lookup
    - update_info_slots
> unlockable

## unlockable
> unlockable
    - slot{"unlockable": true, "input_supported": "web_form"}
    - utter_ask_order
* affirm
> unlock

## unlockable
> unlockable
    - slot{"unlockable": true, "input_supported": "text"}
    - utter_ask_order
* affirm
> unlock

## unlockable
> unlockable
    - slot{"unlockable": true, "input_supported": "voice", "highest_input_supported": "web_form"}
    - utter_ask_order
* affirm
> unlock

## unlockable
> unlockable
    - slot{"unlockable": true, "input_supported": "voice", "highest_input_supported": "voice"}
    - utter_order_not_available
> anything_else

## unlock - sign in
> unlock
    - slot{"sign_in_supported": true}
    - sign_in
> unlock_sign_in

## unlock - sign in success
> unlock_sign_in
* sign_in
> unlock_order

## unlock - sign in error
> unlock_sign_in
* sign_in_error
  - utter_sign_in_error
> anything_else

## unlock - sign in cancel
> unlock_sign_in
* sign_in_cancelled
> anything_else

## unlock - no sign in
> unlock
    - slot{"sign_in_supported": false}
> unlock_order

## unlock order
> unlock_order
    - update_info_slots
    - utter_unlock_explain
> unlock_order_form

## unlock order form
> unlock_order_form
    - slot{"input_supported": "text"}
    - unlock_order_form
    - unlock_order
    - unlock_clear
> anything_else

## unlock order web form
> unlock_order_form
    - slot{"input_supported": "web_form"}
    - unlock_order_web_form

## unlock order move
> unlock_order_form
    - slot{"input_supported": "voice"}
    - move_to_web_form_device
* move_to_new_device_refused
> anything_else

## unlock order move
> unlock_order_form
    - slot{"input_supported": "voice"}
    - move_to_web_form_device
* moved_to_new_device
    - update_info_slots
> unlock_order_form

## not unlockable
> unlockable
    - slot{"unlockable": false}
    - unlock_clear
> anything_else

## interactive_story_2
* support_location
    - support_location
> anything_else

## interactive_story_3
* greet
    - action_deactivate_form
    - update_info_slots
    - greet
* greet
    - update_info_slots
    - greet
* support_location
    - support_location
    - utter_anything_else
* affirm
* support_opening_hours
    - support_opening_hours
    - utter_anything_else
* deny
    - utter_goodbye
* support_opening_hours
    - support_opening_hours
    - utter_anything_else
* affirm
* support_contact_phone
    - support_contact_phone
> anything_else

## interactive_story_5
* support_location
    - support_location
    - utter_anything_else
* affirm
* support_location
    - support_location
> anything_else

## interactive_story_1
* greet
    - action_deactivate_form
    - update_info_slots
    - greet
* support_opening_hours
    - support_opening_hours
    - utter_anything_else
* affirm
    - utter_can_do
* repair
    - repair_form
    - form{"name": "repair_form"}
    - form{"name": null}
    - repair
> repairable