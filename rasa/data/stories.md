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
  - utter_cheer_up

## next question no
> anything_else
    - utter_anything_else
* deny
    - utter_goodbye
> rate

## next question ys
> anything_else
    - utter_anything_else
* affirm
    - utter_can_do

## end
* end
  - utter_goodbye
> rate
    
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
  - request_human
  - pause
    
## cant help - no
> cant_help    
  - utter_cant_help
* deny
  - utter_can_do
    
## Out of scope
* out_of_scope
> cant_help

  
## request_human
* request_human OR stop
    - request_human
    - pause
  
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
> anything_else

## unlock
* unlock
    - unlock_clear
    - utter_unlock_explain
    - unlock_form
    - form{"name": "repair_form"}
    - form{"name": null}
    - unlock_lookup
> unlockable

## unlockable
> unlockable
    - slot{"unlockable": true}
    - utter_ask_order
* affirm
    - unlock_order

## unlockable
> unlockable
    - slot{"unlockable": true}
    - utter_ask_order
* deny
    - unlock_clear
> anything_else

## not unlockable
> unlockable
    - slot{"unlockable": false}
> anything_else

## interactive_story_1
* repair{"brand": "iPhone"}
    - slot{"brand": "iPhone"}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"brand": "iPhone"}
    - slot{"brand": "iPhone"}
    - slot{"requested_slot": "iphone_model"}
* form: iphone_model{"iphone_model": "iPhone 4S"}
    - slot{"iphone_model": "iPhone 4S"}
    - form: repair_form
    - slot{"iphone_model": "iPhone 4S"}
    - slot{"requested_slot": "iphone_repair"}
* form: repair{"iphone_repair": "battery"}
    - slot{"iphone_repair": "battery"}
    - form: repair_form
    - slot{"iphone_repair": "battery"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
* repair{"iphone_model": "iphone 5s"}
    - slot{"iphone_model": "iphone 5s"}
    - slot{"iphone_repair": null}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"iphone_repair": "battery"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
* repair{"iphone_repair": "screen"}
    - slot{"iphone_repair": "screen"}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"iphone_repair": "screen"}
    - slot{"iphone_repair": "screen"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
> anything_else

## interactive_story_1
* repair{"brand": "iPhone"}
    - slot{"brand": "iPhone"}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"brand": "iPhone"}
    - slot{"brand": "iPhone"}
    - slot{"requested_slot": "iphone_model"}
* form: iphone_model{"iphone_model": "iPhone 4S"}
    - slot{"iphone_model": "iPhone 4S"}
    - form: repair_form
    - slot{"iphone_model": "iPhone 4S"}
    - slot{"requested_slot": "iphone_repair"}
* form: repair{"iphone_repair": "battery"}
    - slot{"iphone_repair": "battery"}
    - form: repair_form
    - slot{"iphone_repair": "battery"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
* repair{"iphone_model": "ipad air"}
    - slot{"iphone_model": "ipad air"}
    - slot{"brand": "ipad"}
    - slot{"iphone_repair": null}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"iphone_repair": "battery"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
* repair{"iphone_repair": "screen"}
    - slot{"iphone_repair": "screen"}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"iphone_repair": "screen"}
    - slot{"iphone_repair": "screen"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
> anything_else

## interactive_story_2
* support_location
    - support_location
> anything_else

## interactive_story_3
* greet
    - greet
* greet
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

## interactive_story_6
* end
    - utter_goodbye
* rate{"rating": "9", "CARDINAL": "9"}
    - slot{"rating": "9"}
    - rate_form
    - form{"name": "rate_form"}
    - slot{"rating": 9}
    - slot{"rating": 9}
    - form{"name": null}
    - slot{"requested_slot": null}
    - utter_thanks_end

## interactive_story_7
* end
    - utter_goodbye
* rate{"rating": "10", "CARDINAL": "10"}
    - slot{"rating": "10"}
    - rate_form
    - form{"name": "rate_form"}
    - slot{"rating": 10}
    - slot{"rating": 10}
    - form{"name": null}
    - slot{"requested_slot": null}
    - utter_thanks_end

## interactive_story_8
* repair{"iphone_model": "iphone 6", "CARDINAL": "6"}
    - slot{"iphone_model": "iphone 6"}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"requested_slot": "iphone_repair"}
* form: repair{"iphone_repair": "screen"}
    - slot{"iphone_repair": "screen"}
    - form: repair_form
    - slot{"iphone_repair": "screen"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
> anything_else

## interactive_story_9
* repair{"iphone_model": "iPhone 7+", "iphone_repair": "battery", "PRODUCT": "iPhone 7+"}
    - slot{"iphone_model": "iPhone 7+"}
    - slot{"iphone_repair": "battery"}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"iphone_repair": "battery"}
    - slot{"iphone_repair": "battery"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
> anything_else

## interactive_story_10
* repair{"brand": "iPad"}
    - slot{"brand": "iPad"}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"brand": "iPad"}
    - slot{"brand": "iPad"}
    - slot{"requested_slot": "ipad_model"}
* form: ipad_model{"ipad_model": "iPad air"}
    - slot{"ipad_model": "iPad air"}
    - form: repair_form
    - slot{"ipad_model": "iPad air"}
    - slot{"requested_slot": "iphone_repair"}
* form: repair{"iphone_repair": "battery"}
    - slot{"iphone_repair": "battery"}
    - form: repair_form
    - slot{"iphone_repair": "battery"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
> anything_else

## interactive_story_11
* repair{"brand": "Samsung"}
    - slot{"brand": "Samsung"}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"brand": "Samsung"}
    - slot{"brand": "Samsung"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
> anything_else

## interactive_story_12
* repair{"iphone_model": "iphone 6", "iphone_repair": "battery", "CARDINAL": "6"}
    - slot{"iphone_model": "iphone 6"}
    - slot{"iphone_repair": "battery"}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"iphone_repair": "battery"}
    - slot{"iphone_repair": "battery"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
> anything_else

## interactive_story_1
* repair{"iphone_model": "iphone 6", "iphone_repair": "battery", "CARDINAL": "6"}
    - slot{"iphone_model": "iphone 6"}
    - slot{"iphone_repair": "battery"}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"iphone_repair": "battery"}
    - slot{"iphone_repair": "battery"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
> anything_else

## interactive_story_1
* repair{"iphone_model": "iphone 6", "iphone_repair": "battery", "CARDINAL": "6"}
    - slot{"iphone_model": "iphone 6"}
    - slot{"iphone_repair": "battery"}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"iphone_repair": "battery"}
    - slot{"iphone_repair": "battery"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
> anything_else

## interactive_story_1
* greet
    - greet
* support_opening_hours
    - support_opening_hours
    - utter_anything_else
* affirm
    - utter_can_do
* repair{"iphone_model": "iPhone 6S", "iphone_repair": "battery", "number": 6}
    - slot{"iphone_model": "iPhone 6S"}
    - slot{"iphone_repair": "battery"}
    - repair_form
    - form{"name": "repair_form"}
    - slot{"iphone_repair": "battery"}
    - slot{"iphone_repair": "battery"}
    - form{"name": null}
    - slot{"requested_slot": null}
    - repair
    - utter_anything_else
* deny
    - utter_goodbye
