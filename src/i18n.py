"""Kitchen-mode labels and messages in English, Hindi and Tamil.

One dictionary: key -> {"en", "hi", "ta"}. Placeholders like {food} must be the
same in every language (a test checks this). Food names and units stay in
English. Project-insights pages are not translated.
"""

from __future__ import annotations

import string

LANGUAGES = {"en": "English", "hi": "हिन्दी", "ta": "தமிழ்"}

STRINGS: dict[str, dict[str, str]] = {
    # --- navigation and modes -------------------------------------------------
    "language": {"en": "Language", "hi": "भाषा", "ta": "மொழி"},
    "nav_home": {"en": "Home", "hi": "होम", "ta": "முகப்பு"},
    "nav_bought": {"en": "I bought…", "hi": "मैंने खरीदा…", "ta": "நான் வாங்கியது…"},
    "nav_pantry": {"en": "Pantry check", "hi": "रसोई जाँच", "ta": "சமையலறை சரிபார்ப்பு"},
    "nav_shopping": {"en": "Shopping list", "hi": "खरीदारी सूची", "ta": "வாங்கும் பட்டியல்"},
    "nav_my_data": {"en": "My data", "hi": "मेरा डेटा", "ta": "என் தரவு"},
    "section_kitchen": {"en": "Kitchen", "hi": "रसोई", "ta": "சமையலறை"},
    "section_insights": {"en": "Project insights", "hi": "प्रोजेक्ट विश्लेषण", "ta": "திட்ட பகுப்பாய்வு"},
    "switch_to_insights": {"en": "Open Project insights", "hi": "प्रोजेक्ट विश्लेषण खोलें",
                           "ta": "திட்ட பகுப்பாய்வைத் திற"},
    "switch_insights_help": {"en": "Charts and models from the data-science project.",
                             "hi": "डेटा-साइंस प्रोजेक्ट के चार्ट और मॉडल।",
                             "ta": "தரவு அறிவியல் திட்டத்தின் வரைபடங்களும் மாதிரிகளும்."},
    "switch_to_kitchen": {"en": "Back to Kitchen", "hi": "रसोई पर वापस", "ta": "சமையலறைக்குத் திரும்பு"},
    "switch_kitchen_help": {"en": "Log food, check the pantry and get your shopping list.",
                            "hi": "खाना लिखें, रसोई जाँचें और खरीदारी सूची पाएँ।",
                            "ta": "உணவைப் பதிவு செய்யுங்கள், சமையலறையைச் சரிபாருங்கள், வாங்கும் பட்டியலைப் பெறுங்கள்."},

    # --- home ------------------------------------------------------------------
    "home_purpose": {"en": "What needs your attention today.", "hi": "आज किन चीज़ों पर ध्यान देना है।",
                     "ta": "இன்று கவனிக்க வேண்டியவை."},
    "start_title": {"en": "Start by logging what you buy", "hi": "शुरुआत करें: जो खरीदा, उसे लिखें",
                    "ta": "நீங்கள் வாங்கியதைப் பதிவு செய்து தொடங்குங்கள்"},
    "start_body": {"en": "Each time you shop, tap I bought… Once a week, do a pantry check. FORAGE then tells you "
                         "what to use first and what to buy.",
                   "hi": "हर बार खरीदारी के बाद “मैंने खरीदा…” दबाएँ। हफ़्ते में एक बार रसोई जाँच करें। फिर FORAGE "
                         "बताएगा कि पहले क्या इस्तेमाल करें और क्या खरीदें।",
                   "ta": "ஒவ்வொரு முறை கடைக்குச் சென்ற பிறகும் “நான் வாங்கியது…” அழுத்துங்கள். வாரம் ஒருமுறை "
                         "சமையலறை சரிபார்ப்பு செய்யுங்கள். பிறகு எதை முதலில் பயன்படுத்த வேண்டும், எதை வாங்க "
                         "வேண்டும் என்று FORAGE சொல்லும்."},
    "log_purchase": {"en": "Log a purchase", "hi": "खरीदारी लिखें", "ta": "வாங்கியதைப் பதிவு செய்"},
    "this_month": {"en": "This month", "hi": "इस महीने", "ta": "இந்த மாதம்"},
    "wasted_month": {"en": "About ₹{amount} of food was thrown away this month.",
                     "hi": "इस महीने लगभग ₹{amount} का खाना फेंका गया।",
                     "ta": "இந்த மாதம் சுமார் ₹{amount} மதிப்புள்ள உணவு வீணானது."},
    "no_waste_month": {"en": "No food thrown away this month so far.",
                       "hi": "इस महीने अब तक कोई खाना नहीं फेंका गया।",
                       "ta": "இந்த மாதம் இதுவரை உணவு எதுவும் வீணாகவில்லை."},
    "spent_month": {"en": "You spent ₹{amount} on food this month.", "hi": "इस महीने आपने खाने पर ₹{amount} खर्च किए।",
                    "ta": "இந்த மாதம் உணவுக்கு ₹{amount} செலவழித்தீர்கள்."},
    "use_first": {"en": "Use first", "hi": "पहले इस्तेमाल करें", "ta": "முதலில் பயன்படுத்துங்கள்"},
    "use_today": {"en": "Use the {food} today.", "hi": "{food} आज ही इस्तेमाल करें।",
                  "ta": "{food} இன்றே பயன்படுத்துங்கள்."},
    "use_tomorrow": {"en": "Use the {food} by tomorrow.", "hi": "{food} कल तक इस्तेमाल करें।",
                     "ta": "{food} நாளைக்குள் பயன்படுத்துங்கள்."},
    "use_in_days": {"en": "Use the {food} within {days} days.", "hi": "{food} {days} दिनों में इस्तेमाल करें।",
                    "ta": "{food} {days} நாட்களுக்குள் பயன்படுத்துங்கள்."},
    "nothing_expiring": {"en": "Nothing needs using up in the next 3 days.",
                         "hi": "अगले 3 दिनों में कुछ भी खराब नहीं होने वाला।",
                         "ta": "அடுத்த 3 நாட்களில் கெடக்கூடியது எதுவும் இல்லை."},
    "at_risk": {"en": "You may not finish the {food} in time (about ₹{amount}). Use it first or share it.",
                "hi": "{food} शायद समय पर खत्म न हो (लगभग ₹{amount})। इसे पहले इस्तेमाल करें या किसी को दे दें।",
                "ta": "{food} நேரத்திற்குள் தீராமல் போகலாம் (சுமார் ₹{amount}). இதை முதலில் பயன்படுத்துங்கள் "
                      "அல்லது பகிர்ந்து கொடுங்கள்."},
    "at_risk_plain": {"en": "You may not finish the {food} in time. Use it first or share it.",
                      "hi": "{food} शायद समय पर खत्म न हो। इसे पहले इस्तेमाल करें या किसी को दे दें।",
                      "ta": "{food} நேரத்திற்குள் தீராமல் போகலாம். இதை முதலில் பயன்படுத்துங்கள் அல்லது "
                            "பகிர்ந்து கொடுங்கள்."},
    "shopping_head": {"en": "This week's shopping", "hi": "इस हफ़्ते की खरीदारी", "ta": "இந்த வார வாங்குதல்"},
    "to_buy_count": {"en": "{n} things to buy this week.", "hi": "इस हफ़्ते {n} चीज़ें खरीदनी हैं।",
                     "ta": "இந்த வாரம் {n} பொருட்கள் வாங்க வேண்டும்."},
    "to_buy_none": {"en": "You have enough of everything for this week.", "hi": "इस हफ़्ते के लिए सब कुछ पर्याप्त है।",
                    "ta": "இந்த வாரத்திற்குத் தேவையானவை எல்லாம் உள்ளன."},
    "enough_skip": {"en": "You have enough {food}, skip it this week.", "hi": "{food} काफ़ी है, इस हफ़्ते न खरीदें।",
                    "ta": "{food} போதுமான அளவு உள்ளது, இந்த வாரம் வாங்க வேண்டாம்."},
    "open_list": {"en": "Open the shopping list", "hi": "खरीदारी सूची खोलें", "ta": "வாங்கும் பட்டியலைத் திற"},
    "list_after_check": {"en": "Your shopping list appears after your first pantry check.",
                         "hi": "पहली रसोई जाँच के बाद आपकी खरीदारी सूची दिखेगी।",
                         "ta": "முதல் சமையலறை சரிபார்ப்புக்குப் பிறகு உங்கள் வாங்கும் பட்டியல் தோன்றும்."},
    "smarter_after": {"en": "Keep checking your pantry each week: the list gets more accurate after {weeks} more "
                            "week{s}.",
                      "hi": "हर हफ़्ते रसोई जाँचते रहें: {weeks} और हफ़्तों के बाद सूची और सही हो जाएगी।",
                      "ta": "ஒவ்வொரு வாரமும் சரிபார்த்துக் கொண்டே இருங்கள்: இன்னும் {weeks} வாரங்களில் "
                            "பட்டியல் மேலும் துல்லியமாகும்."},
    "last_check": {"en": "Last pantry check: {date}.", "hi": "पिछली रसोई जाँच: {date}।",
                   "ta": "கடைசி சரிபார்ப்பு: {date}."},
    "check_due": {"en": "It has been {days} days since your last pantry check. A quick check keeps your list right.",
                  "hi": "पिछली रसोई जाँच को {days} दिन हो गए। जल्दी से जाँच कर लें ताकि सूची सही रहे।",
                  "ta": "கடைசி சரிபார்ப்புக்குப் பிறகு {days} நாட்கள் ஆகிவிட்டன. பட்டியல் சரியாக இருக்க ஒரு "
                        "விரைவான சரிபார்ப்பு செய்யுங்கள்."},
    "no_check_yet": {"en": "Do your first pantry check so FORAGE can learn how fast you use each food.",
                     "hi": "पहली रसोई जाँच करें ताकि FORAGE सीख सके कि आप हर चीज़ कितनी जल्दी इस्तेमाल करते हैं।",
                     "ta": "ஒவ்வொரு பொருளையும் நீங்கள் எவ்வளவு வேகமாகப் பயன்படுத்துகிறீர்கள் என்று FORAGE "
                           "அறிய, முதல் சமையலறை சரிபார்ப்பைச் செய்யுங்கள்."},

    # --- first-time walkthrough -----------------------------------------------
    "walk_step": {"en": "Step {i} of {n}", "hi": "चरण {i} / {n}", "ta": "படி {i} / {n}"},
    "walk1_title": {"en": "Log what you buy", "hi": "जो खरीदें, उसे लिखें", "ta": "வாங்குவதைப் பதிவு செய்யுங்கள்"},
    "walk1_body": {"en": "After shopping, tap I bought… and pick the food and the amount. It takes a few seconds.",
                   "hi": "खरीदारी के बाद “मैंने खरीदा…” दबाएँ और चीज़ व मात्रा चुनें। इसमें कुछ ही सेकंड लगते हैं।",
                   "ta": "கடைக்குச் சென்று வந்ததும் “நான் வாங்கியது…” அழுத்தி, பொருளையும் அளவையும் "
                         "தேர்ந்தெடுங்கள். சில வினாடிகளே ஆகும்."},
    "walk2_title": {"en": "Check your pantry weekly", "hi": "हर हफ़्ते रसोई जाँचें", "ta": "வாரம் ஒருமுறை சரிபார்க்கவும்"},
    "walk2_body": {"en": "Once a week, open Pantry check and tap Full, Half, Almost empty or Finished for each food.",
                   "hi": "हफ़्ते में एक बार “रसोई जाँच” खोलें और हर चीज़ के लिए भरा, आधा, लगभग खाली या खत्म दबाएँ।",
                   "ta": "வாரம் ஒருமுறை “சமையலறை சரிபார்ப்பு” திறந்து, ஒவ்வொரு பொருளுக்கும் முழுதாக, பாதி, "
                         "கிட்டத்தட்ட காலி அல்லது தீர்ந்தது என்பதைத் தொடுங்கள்."},
    "walk3_title": {"en": "Get a smart shopping list", "hi": "स्मार्ट खरीदारी सूची पाएँ",
                    "ta": "ஸ்மார்ட் வாங்கும் பட்டியலைப் பெறுங்கள்"},
    "walk3_body": {"en": "FORAGE learns how fast you use each food, tells you what to use first and lists what to "
                         "buy, in everyday amounts you can share on WhatsApp.",
                   "hi": "FORAGE सीखता है कि आप हर चीज़ कितनी जल्दी इस्तेमाल करते हैं, बताता है कि पहले क्या "
                         "इस्तेमाल करें, और खरीदारी की सूची बनाता है जिसे आप WhatsApp पर भेज सकते हैं।",
                   "ta": "ஒவ்வொரு பொருளையும் நீங்கள் எவ்வளவு வேகமாகப் பயன்படுத்துகிறீர்கள் என்று FORAGE "
                         "கற்றுக்கொள்கிறது; எதை முதலில் பயன்படுத்த வேண்டும் என்று சொல்கிறது; WhatsApp-இல் "
                         "பகிரக்கூடிய வாங்கும் பட்டியலைத் தயாரிக்கிறது."},
    "next": {"en": "Next", "hi": "आगे", "ta": "அடுத்து"},
    "skip": {"en": "Skip", "hi": "छोड़ें", "ta": "தவிர்"},
    "start": {"en": "Start", "hi": "शुरू करें", "ta": "தொடங்கு"},

    # --- I bought… -------------------------------------------------------------
    "bought_purpose": {"en": "Tap a food, choose how much, save.", "hi": "चीज़ चुनें, मात्रा चुनें, सेव करें।",
                       "ta": "பொருளைத் தொட்டு, அளவைத் தேர்ந்தெடுத்து, சேமியுங்கள்."},
    "your_foods": {"en": "Your usual foods", "hi": "आपकी रोज़ की चीज़ें", "ta": "நீங்கள் வழக்கமாக வாங்குபவை"},
    "starter_foods": {"en": "Common foods", "hi": "आम चीज़ें", "ta": "பொதுவான பொருட்கள்"},
    "search_food": {"en": "Another food (search, or type a new one)", "hi": "कोई और चीज़ (खोजें या नई लिखें)",
                    "ta": "வேறு பொருள் (தேடுங்கள் அல்லது புதியதை எழுதுங்கள்)"},
    "search_placeholder": {"en": "e.g. Paneer", "hi": "जैसे Paneer", "ta": "உதா. Paneer"},
    "how_much": {"en": "How much?", "hi": "कितना?", "ta": "எவ்வளவு?"},
    "other_amount": {"en": "Other amount", "hi": "दूसरी मात्रा", "ta": "வேறு அளவு"},
    "amount": {"en": "Amount", "hi": "मात्रा", "ta": "அளவு"},
    "unit": {"en": "Unit", "hi": "इकाई", "ta": "அலகு"},
    "price_paid": {"en": "Price paid (₹, optional)", "hi": "कीमत (₹, ज़रूरी नहीं)", "ta": "செலுத்திய விலை (₹, விருப்பம்)"},
    "price_help": {"en": "The total you paid for this, not the price per kg.",
                   "hi": "इसके लिए कुल कितने दिए, प्रति किलो की कीमत नहीं।",
                   "ta": "இதற்காக மொத்தம் செலுத்தியது, ஒரு கிலோ விலை அல்ல."},
    "another_day": {"en": "Bought on another day?", "hi": "किसी और दिन खरीदा?", "ta": "வேறு நாளில் வாங்கினீர்களா?"},
    "date": {"en": "Date", "hi": "तारीख", "ta": "தேதி"},
    "new_food_note": {"en": "New food: these help FORAGE warn you before it goes off.",
                      "hi": "नई चीज़: इससे FORAGE खराब होने से पहले बता पाएगा।",
                      "ta": "புதிய பொருள்: இது கெடுவதற்கு முன் FORAGE எச்சரிக்க உதவும்."},
    "category": {"en": "Type of food", "hi": "किस तरह की चीज़", "ta": "உணவு வகை"},
    "stays_good": {"en": "Days it stays good", "hi": "कितने दिन ठीक रहती है", "ta": "எத்தனை நாள் நன்றாக இருக்கும்"},
    "save": {"en": "Save", "hi": "सेव करें", "ta": "சேமி"},
    "saved_purchase": {"en": "Saved: {food}, {amount}{price}.", "hi": "सेव हो गया: {food}, {amount}{price}।",
                       "ta": "சேமிக்கப்பட்டது: {food}, {amount}{price}."},
    "choose_food_first": {"en": "Tap a food first.", "hi": "पहले कोई चीज़ चुनें।",
                          "ta": "முதலில் ஒரு பொருளைத் தேர்ந்தெடுங்கள்."},
    "choose_amount_first": {"en": "Choose how much you bought.", "hi": "कितना खरीदा, यह चुनें।",
                            "ta": "எவ்வளவு வாங்கினீர்கள் என்று தேர்ந்தெடுங்கள்."},
    "amount_positive": {"en": "The amount must be more than 0.", "hi": "मात्रा 0 से ज़्यादा होनी चाहिए।",
                        "ta": "அளவு 0-க்கு மேல் இருக்க வேண்டும்."},
    "change_food": {"en": "Change food", "hi": "चीज़ बदलें", "ta": "பொருளை மாற்று"},
    "repeat_last": {"en": "Repeat last purchase ({food}, {amount})", "hi": "पिछली खरीदारी दोहराएँ ({food}, {amount})",
                    "ta": "கடைசி வாங்குதலை மீண்டும் ({food}, {amount})"},
    "repeat_week": {"en": "Repeat last week ({n} items)", "hi": "पिछला हफ़्ता दोहराएँ ({n} चीज़ें)",
                    "ta": "கடந்த வாரத்தை மீண்டும் ({n} பொருட்கள்)"},
    "repeat_week_title": {"en": "Repeat last week's shopping", "hi": "पिछले हफ़्ते की खरीदारी दोहराएँ",
                          "ta": "கடந்த வார வாங்குதலை மீண்டும் செய்"},
    "repeat_week_body": {"en": "Add these {n} items again, dated today?", "hi": "ये {n} चीज़ें आज की तारीख से दोबारा जोड़ें?",
                         "ta": "இந்த {n} பொருட்களை இன்றைய தேதியில் மீண்டும் சேர்க்கவா?"},
    "add_them": {"en": "Add them", "hi": "जोड़ें", "ta": "சேர்"},
    "cancel": {"en": "Cancel", "hi": "रद्द करें", "ta": "ரத்து"},
    "saved_many": {"en": "Saved {n} purchases.", "hi": "{n} खरीदारी सेव हो गईं।", "ta": "{n} வாங்குதல்கள் சேமிக்கப்பட்டன."},
    "paste_bill": {"en": "Paste a shopping bill", "hi": "बिल पेस्ट करें", "ta": "கடை பில்லை ஒட்டவும்"},
    "bill_help": {"en": "One item per line, ending with the price, e.g. Milk 2 L 120. You check the rows before "
                        "anything is saved.",
                  "hi": "हर लाइन में एक चीज़, आख़िर में कीमत, जैसे Milk 2 L 120। सेव करने से पहले आप लाइनें जाँच सकते हैं।",
                  "ta": "ஒரு வரிக்கு ஒரு பொருள், கடைசியில் விலை, உதா. Milk 2 L 120. சேமிப்பதற்கு முன் வரிகளைச் "
                        "சரிபார்க்கலாம்."},
    "read_bill": {"en": "Read the bill", "hi": "बिल पढ़ें", "ta": "பில்லைப் படி"},
    "paste_first": {"en": "Paste the bill text first.", "hi": "पहले बिल का टेक्स्ट पेस्ट करें।",
                    "ta": "முதலில் பில் உரையை ஒட்டவும்."},
    "not_read": {"en": "Not read: {lines}", "hi": "पढ़ा नहीं गया: {lines}", "ta": "படிக்க முடியவில்லை: {lines}"},
    "nothing_recognised": {"en": "No items were recognised.", "hi": "कोई चीज़ पहचानी नहीं गई।",
                           "ta": "எந்தப் பொருளும் அடையாளம் காணப்படவில்லை."},
    "save_n": {"en": "Save {n} purchases", "hi": "{n} खरीदारी सेव करें", "ta": "{n} வாங்குதல்களைச் சேமி"},
    "recent": {"en": "Recently bought", "hi": "हाल में खरीदा", "ta": "சமீபத்தில் வாங்கியவை"},
    "today": {"en": "Today", "hi": "आज", "ta": "இன்று"},
    "yesterday": {"en": "Yesterday", "hi": "कल", "ta": "நேற்று"},
    "edit_on_my_data": {"en": "Change or delete entries on My data.", "hi": "बदलने या मिटाने के लिए “मेरा डेटा” खोलें।",
                        "ta": "மாற்ற அல்லது நீக்க “என் தரவு” பக்கத்தைத் திறக்கவும்."},

    # --- pantry check ----------------------------------------------------------
    "pantry_purpose": {"en": "Look in your fridge and cupboards and tap how much is left. Weekly is enough.",
                       "hi": "फ्रिज और अलमारी में देखें और बताएँ कितना बचा है। हफ़्ते में एक बार काफ़ी है।",
                       "ta": "ஃபிரிட்ஜ் மற்றும் அலமாரிகளில் பார்த்து, எவ்வளவு மீதம் உள்ளது என்று தொடுங்கள். வாரம் "
                             "ஒருமுறை போதும்."},
    "nothing_to_check": {"en": "Nothing to check yet", "hi": "अभी जाँचने को कुछ नहीं",
                         "ta": "இப்போது சரிபார்க்க எதுவும் இல்லை"},
    "nothing_to_check_body": {"en": "Log a purchase first; the foods you buy appear here.",
                              "hi": "पहले कोई खरीदारी लिखें; खरीदी चीज़ें यहाँ दिखेंगी।",
                              "ta": "முதலில் ஒரு வாங்குதலைப் பதிவு செய்யுங்கள்; வாங்கிய பொருட்கள் இங்கே தோன்றும்."},
    "check_everything": {"en": "Check everything ({n} foods)", "hi": "सब जाँचें ({n} चीज़ें)",
                         "ta": "எல்லாவற்றையும் சரிபார் ({n} பொருட்கள்)"},
    "check_one": {"en": "Or check one food", "hi": "या एक चीज़ जाँचें", "ta": "அல்லது ஒரு பொருளைச் சரிபார்"},
    "other_food": {"en": "Another food", "hi": "कोई और चीज़", "ta": "வேறு பொருள்"},
    "progress": {"en": "{i} of {n}", "hi": "{n} में से {i}", "ta": "{n}-இல் {i}"},
    "full_is": {"en": "Full means about {amount}: what you had at the last check plus what you bought since.",
                "hi": "“भरा” यानी लगभग {amount}: पिछली जाँच में जितना था और उसके बाद जितना खरीदा।",
                "ta": "“முழுதாக” என்றால் சுமார் {amount}: கடைசி சரிபார்ப்பில் இருந்ததும் அதன் பிறகு வாங்கியதும்."},
    "thrown_q": {"en": "Thrown any away?", "hi": "कुछ फेंका?", "ta": "ஏதாவது வீணாக்கினீர்களா?"},
    "waste_nothing": {"en": "Nothing", "hi": "कुछ नहीं", "ta": "எதுவும் இல்லை"},
    "waste_a_little": {"en": "A little", "hi": "थोड़ा", "ta": "கொஞ்சம்"},
    "waste_about_half": {"en": "About half", "hi": "लगभग आधा", "ta": "சுமார் பாதி"},
    "how_much_left": {"en": "How much is left?", "hi": "कितना बचा है?", "ta": "எவ்வளவு மீதம் உள்ளது?"},
    "level_full": {"en": "Full", "hi": "भरा", "ta": "முழுதாக"},
    "level_half": {"en": "Half", "hi": "आधा", "ta": "பாதி"},
    "level_almost_empty": {"en": "Almost empty", "hi": "लगभग खाली", "ta": "கிட்டத்தட்ட காலி"},
    "level_finished": {"en": "Finished", "hi": "खत्म", "ta": "தீர்ந்தது"},
    "exact_amount": {"en": "Exact amount", "hi": "सही मात्रा लिखें", "ta": "சரியான அளவு"},
    "left_now": {"en": "Left now ({unit})", "hi": "अभी बचा ({unit})", "ta": "இப்போது மீதம் ({unit})"},
    "thrown_away": {"en": "Thrown away ({unit})", "hi": "फेंका ({unit})", "ta": "வீணானது ({unit})"},
    "save_check": {"en": "Save check", "hi": "जाँच सेव करें", "ta": "சரிபார்ப்பைச் சேமி"},
    "skip_food": {"en": "Skip this food", "hi": "यह छोड़ें", "ta": "இதைத் தவிர்"},
    "stop_checking": {"en": "Stop", "hi": "रोकें", "ta": "நிறுத்து"},
    "saved_check": {"en": "Saved: {food}, {left} left.", "hi": "सेव हो गया: {food}, {left} बचा।",
                    "ta": "சேமிக்கப்பட்டது: {food}, {left} மீதம்."},
    "all_done": {"en": "All done: {n} foods checked.", "hi": "हो गया: {n} चीज़ें जाँची गईं।",
                 "ta": "முடிந்தது: {n} பொருட்கள் சரிபார்க்கப்பட்டன."},
    "too_much": {"en": "{food}: {left} left + {wasted} thrown away is more than the {available} you had.",
                 "hi": "{food}: {left} बचा + {wasted} फेंका, यह आपके पास मौजूद {available} से ज़्यादा है।",
                 "ta": "{food}: {left} மீதம் + {wasted} வீணானது, உங்களிடம் இருந்த {available}-ஐ விட அதிகம்."},
    "not_negative": {"en": "Amounts must be 0 or more.", "hi": "मात्रा 0 या उससे ज़्यादा होनी चाहिए।",
                     "ta": "அளவுகள் 0 அல்லது அதற்கு மேல் இருக்க வேண்டும்."},
    "checked_another_day": {"en": "Checked on another day?", "hi": "किसी और दिन जाँचा?",
                            "ta": "வேறு நாளில் சரிபார்த்தீர்களா?"},
    "how_it_works": {"en": "How this works", "hi": "यह कैसे काम करता है", "ta": "இது எப்படி வேலை செய்கிறது"},
    "how_it_works_body": {"en": "You never type how much you ate: FORAGE works it out from what you bought and what "
                                "is left. The more regularly you check, the better your shopping list.",
                          "hi": "आपको यह नहीं लिखना कि कितना खाया: FORAGE खरीदी और बची चीज़ों से इसका हिसाब लगाता "
                                "है। जितनी नियमित जाँच करेंगे, सूची उतनी अच्छी होगी।",
                          "ta": "எவ்வளவு சாப்பிட்டீர்கள் என்று நீங்கள் எழுத வேண்டியதில்லை: வாங்கியதையும் மீதம் "
                                "உள்ளதையும் வைத்து FORAGE கணக்கிடுகிறது. தவறாமல் சரிபார்த்தால் பட்டியல் "
                                "சிறப்பாக இருக்கும்."},

    # --- shopping list ---------------------------------------------------------
    "shop_purpose": {"en": "What to buy this week, and how much.", "hi": "इस हफ़्ते क्या और कितना खरीदना है।",
                     "ta": "இந்த வாரம் என்ன, எவ்வளவு வாங்க வேண்டும்."},
    "buy_these": {"en": "Buy", "hi": "खरीदें", "ta": "வாங்க வேண்டியவை"},
    "skip_these": {"en": "Skip this week", "hi": "इस हफ़्ते न खरीदें", "ta": "இந்த வாரம் வேண்டாம்"},
    "share_list": {"en": "Share list", "hi": "सूची भेजें", "ta": "பட்டியலைப் பகிர்"},
    "share_help": {"en": "Copy the text below (copy button on the right), or send it straight to WhatsApp.",
                   "hi": "नीचे का टेक्स्ट कॉपी करें (दाईं ओर कॉपी बटन), या सीधे WhatsApp पर भेजें।",
                   "ta": "கீழே உள்ள உரையை நகலெடுங்கள் (வலதுபுறம் நகல் பொத்தான்), அல்லது நேரடியாக WhatsApp-க்கு "
                         "அனுப்புங்கள்."},
    "send_whatsapp": {"en": "Send on WhatsApp", "hi": "WhatsApp पर भेजें", "ta": "WhatsApp-இல் அனுப்பு"},
    "share_title": {"en": "Shopping list (FORAGE)", "hi": "खरीदारी सूची (FORAGE)", "ta": "வாங்கும் பட்டியல் (FORAGE)"},
    "list_note": {"en": "Amounts are your usual use for 7 days minus what you still have, rounded up to what you "
                        "can buy.",
                  "hi": "मात्रा = 7 दिनों की आपकी सामान्य खपत में से जो अभी बचा है वह घटाकर, खरीदने लायक मात्रा तक बढ़ाई गई।",
                  "ta": "அளவு = 7 நாட்களுக்கான உங்கள் வழக்கமான பயன்பாட்டில் இப்போது உள்ளதைக் கழித்து, "
                        "வாங்கக்கூடிய அளவுக்கு உயர்த்தப்பட்டது."},
    "nothing_to_buy": {"en": "Nothing to buy this week.", "hi": "इस हफ़्ते कुछ नहीं खरीदना।",
                       "ta": "இந்த வாரம் எதுவும் வாங்க வேண்டாம்."},
    "do_pantry_check": {"en": "Do a pantry check", "hi": "रसोई जाँच करें", "ta": "சமையலறை சரிபார்ப்பு செய்"},

    # --- my data ---------------------------------------------------------------
    "my_data_purpose": {"en": "Everything you have logged. Change or delete entries, download or upload a file.",
                        "hi": "आपने जो कुछ लिखा है। बदलें या मिटाएँ, फ़ाइल डाउनलोड या अपलोड करें।",
                        "ta": "நீங்கள் பதிவு செய்த அனைத்தும். மாற்றலாம், நீக்கலாம், கோப்பைப் பதிவிறக்கலாம் அல்லது "
                              "பதிவேற்றலாம்."},
    "purchases": {"en": "Purchases", "hi": "खरीदारी", "ta": "வாங்குதல்கள்"},
    "pantry_checks": {"en": "Pantry checks", "hi": "रसोई जाँचें", "ta": "சரிபார்ப்புகள்"},
    "foods": {"en": "Foods", "hi": "चीज़ें", "ta": "பொருட்கள்"},
    "files": {"en": "Download and upload", "hi": "डाउनलोड और अपलोड", "ta": "பதிவிறக்கம், பதிவேற்றம்"},
    "analyse_mine": {"en": "See charts of my data", "hi": "मेरे डेटा के चार्ट देखें", "ta": "என் தரவின் வரைபடங்களைப் பார்"},
    "save_changes": {"en": "Save {n} change(s)", "hi": "{n} बदलाव सेव करें", "ta": "{n} மாற்றங்களைச் சேமி"},
    "delete_selected": {"en": "Delete selected ({n})", "hi": "चुने हुए मिटाएँ ({n})", "ta": "தேர்ந்தவற்றை நீக்கு ({n})"},
    "delete_confirm": {"en": "Delete {n} entries? This cannot be undone.", "hi": "{n} एंट्री मिटाएँ? यह वापस नहीं होगा।",
                       "ta": "{n} பதிவுகளை நீக்கவா? இதைத் திரும்பப் பெற முடியாது."},
    "delete": {"en": "Delete", "hi": "मिटाएँ", "ta": "நீக்கு"},
    "no_entries": {"en": "Nothing here yet.", "hi": "अभी यहाँ कुछ नहीं है।", "ta": "இங்கே இன்னும் எதுவும் இல்லை."},

    # --- account, sign-in and help ---------------------------------------------
    "tagline": {"en": "Log what you buy and check your pantry; FORAGE tells you what to use first and what to buy.",
                "hi": "जो खरीदें उसे लिखें और रसोई जाँचें; FORAGE बताएगा कि पहले क्या इस्तेमाल करें और क्या खरीदें।",
                "ta": "வாங்குவதைப் பதிவு செய்து சமையலறையைச் சரிபாருங்கள்; எதை முதலில் பயன்படுத்த வேண்டும், எதை "
                      "வாங்க வேண்டும் என்று FORAGE சொல்லும்."},
    "unverified_note": {"en": "Google may show “this app isn't verified”. That is because FORAGE is a student project "
                              "in testing. It is safe to press Continue.",
                        "hi": "Google “यह ऐप सत्यापित नहीं है” दिखा सकता है। ऐसा इसलिए, क्योंकि FORAGE एक छात्र "
                              "प्रोजेक्ट है जो अभी टेस्टिंग में है। Continue दबाना सुरक्षित है।",
                        "ta": "Google “இந்த ஆப் சரிபார்க்கப்படவில்லை” என்று காட்டலாம். FORAGE சோதனையில் உள்ள ஒரு "
                              "மாணவர் திட்டம் என்பதால் அப்படி வருகிறது. Continue அழுத்துவது பாதுகாப்பானது."},
    "continue_google": {"en": "Continue with Google", "hi": "Google से जारी रखें", "ta": "Google மூலம் தொடரவும்"},
    "private_note": {"en": "Your purchases and pantry checks are private to your account.",
                     "hi": "आपकी खरीदारी और रसोई जाँच सिर्फ़ आपके खाते में रहती है।",
                     "ta": "உங்கள் வாங்குதல்களும் சரிபார்ப்புகளும் உங்கள் கணக்கிற்கு மட்டுமே."},
    "sign_in_prompt": {"en": "Sign in to use your kitchen.", "hi": "अपनी रसोई इस्तेमाल करने के लिए साइन इन करें।",
                       "ta": "உங்கள் சமையலறையைப் பயன்படுத்த உள்நுழையவும்."},
    "signed_in_as": {"en": "Signed in as", "hi": "साइन इन:", "ta": "உள்நுழைந்தவர்:"},
    "log_out": {"en": "Log out", "hi": "लॉग आउट", "ta": "வெளியேறு"},
    "not_allowed_title": {"en": "Access not enabled for this account", "hi": "इस खाते के लिए पहुँच चालू नहीं है",
                          "ta": "இந்தக் கணக்கிற்கு அணுகல் இயக்கப்படவில்லை"},
    "not_allowed_body": {"en": "{email} is not on this FORAGE team's list. Ask the person who runs the app to add "
                               "it, or sign in with another Google account.",
                         "hi": "{email} इस FORAGE टीम की सूची में नहीं है। ऐप चलाने वाले से इसे जोड़ने को कहें, या "
                               "किसी और Google खाते से साइन इन करें।",
                         "ta": "{email} இந்த FORAGE குழுவின் பட்டியலில் இல்லை. ஆப்பை நடத்துபவரிடம் சேர்க்கச் "
                               "சொல்லுங்கள், அல்லது வேறு Google கணக்கில் உள்நுழையுங்கள்."},
    "single_user": {"en": "Single local user. No sign-in configured.",
                    "hi": "एक ही स्थानीय उपयोगकर्ता। साइन-इन सेट नहीं है।",
                    "ta": "ஒரே உள்ளூர் பயனர். உள்நுழைவு அமைக்கப்படவில்லை."},
    "demo_banner": {"en": "Demo mode, data is temporary and resets. No database is configured, so entries are kept "
                          "in a local file on this machine only.",
                    "hi": "डेमो मोड: डेटा अस्थायी है और मिट जाता है। कोई डेटाबेस सेट नहीं है, इसलिए एंट्री सिर्फ़ "
                          "इसी कंप्यूटर की एक फ़ाइल में रहती हैं।",
                    "ta": "டெமோ முறை: தரவு தற்காலிகமானது, அழிந்துவிடும். தரவுத்தளம் அமைக்கப்படவில்லை, எனவே "
                          "பதிவுகள் இந்தக் கணினியில் உள்ள ஒரு கோப்பில் மட்டுமே இருக்கும்."},
    "install_title": {"en": "Install on your phone", "hi": "फ़ोन पर इंस्टॉल करें", "ta": "ஃபோனில் நிறுவுங்கள்"},
    "install_android": {"en": "Android (Chrome): open FORAGE, tap the ⋮ menu at the top right, then “Add to Home "
                              "screen” or “Install app”.",
                        "hi": "Android (Chrome): FORAGE खोलें, ऊपर दाईं ओर ⋮ मेन्यू दबाएँ, फिर “Add to Home screen” "
                              "या “Install app” चुनें।",
                        "ta": "Android (Chrome): FORAGE-ஐத் திறந்து, மேல் வலதுபுறம் உள்ள ⋮ மெனுவைத் தொட்டு, "
                              "“Add to Home screen” அல்லது “Install app” என்பதைத் தேர்ந்தெடுங்கள்."},
    "install_iphone": {"en": "iPhone (Safari): open FORAGE, tap the Share button (a square with an arrow), then "
                             "“Add to Home Screen”.",
                       "hi": "iPhone (Safari): FORAGE खोलें, Share बटन (तीर वाला चौकोर) दबाएँ, फिर “Add to Home "
                             "Screen” चुनें।",
                       "ta": "iPhone (Safari): FORAGE-ஐத் திறந்து, Share பொத்தானை (அம்புக்குறியுடன் கூடிய சதுரம்) "
                             "தொட்டு, “Add to Home Screen” என்பதைத் தேர்ந்தெடுங்கள்."},
    "install_after": {"en": "FORAGE then opens from its own icon, like an app.",
                      "hi": "इसके बाद FORAGE अपने आइकन से ऐप की तरह खुलेगा।",
                      "ta": "அதன் பிறகு FORAGE தனது சொந்த ஐகானிலிருந்து ஒரு ஆப் போலத் திறக்கும்."},
    "db_unreachable": {"en": "Could not reach your saved data. Try again in a minute.",
                       "hi": "आपका सेव किया डेटा नहीं मिल पाया। एक मिनट बाद फिर कोशिश करें।",
                       "ta": "சேமித்த தரவை அடைய முடியவில்லை. ஒரு நிமிடம் கழித்து மீண்டும் முயலவும்."},
}


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def translate(key: str, lang: str = "en", **values) -> str:
    """The text for `key` in `lang` (English if missing), with {placeholders} filled in."""
    entry = STRINGS[key]
    text = entry.get(lang) or entry["en"]
    return text.format(**values) if values else text
