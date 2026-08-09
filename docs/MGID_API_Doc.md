# MGID API — Documentação Oficial

> **Manutenção:** Tier 3 — revisão quando o vendor mudar a API.

The main provisions of REST API
REST API allows you to integrate external applications with Mgid online  
advertising system.
API provides the ability to retrieve, add, and modify the data. Practically each  object in Mgid (whether it's a client, an advertising company, a teaser, etc.) can  be controlled by API. Mgid REST API Request is an HTTP request, which, with  the help of the ways in URL the object to perform the action is specified, and  with the help of parameters the necessary data is passed. Mgid API is a "RESTful  Web API". The API uses the following REST commands:

GET
PUT
PATCH
POST
DELETE
The query parameters are case sensitive.

These commands correspond to certain actions within the Mgid system. Get an item or a collection of items (for example, a list of advertising campaigns):    

Command	Action	Description
POST	Create	Creates a new element (eg, a teaser)
GET	Get (read)   	Retrieve an element or a collection of elements
PUT	Update	Recreate an existing element or a collection of elements
PATCH	Change	Change certain properties of an element
DELETE	Delete	Delete an item or collection of items (eg, move a teaser to recycle bin)
Important! POST and PUT are not interchangeable. Each of the commands fulfills its specific function.
Mgid API URL:
Mgid REST API for clients is available at:

https://api.mgid.com/v1

In general, the query looks like this:
https://api.mgid.com/v1/module/controller/action?parameter_1=value_of_parameter_1&parameter_2=value_of_parameter_2&parameter_3=value_of_parameter_3

 

Identification
For identification the Mgid REST API uses a unique token consisting of 32 characters which is passed in client’s request Authorization header. You should get a valid token from the dashboard.

Every request sent to the Mgid REST API must contain the API token
 

Mgid REST API answer
In response to a request to the REST API server always returns the HTTP response with a status code , depending on the result of the query. 

Answer code	Description
200 OK	The query has been successfully
processed
The format of the returned data

The returned data can be formatted as JSON, or XML.  The default format is JSON. The request header is used to specify the format in which the data is  
returned. The client sends an Accept header, which indicates desired response format:  
Accept: application / xml  
or  
Accept: application / json


Description of the response format is sent in the response header Content Type. The data returned is the answer is a JSON string, which generally looks as follows:  

{
    "element_1":"value_of_element_1",    
    "element_2":"value_of_element_2", 
    "element_3":{
         "property_1_of_element_3":"value_of_property_1_of_element_3",       
         "property_2_of_element_3":[
               "value_1_of_property_2_of_element_3",
               "value_2_of_property_2_of_element_3"
         ]       
     }    

  . . . .  
}
 

If an error has occurred during the execution of the query   the description corresponding to the error is returned, such as:

{ "errors": [ "[_error_description_]" ] }
The data in the responses is returned taking into account the time zone of the client.

 

Working with clients
 

 

Getting information about the current financial status of the client
Method	GET
URL	api.mgid.com/v1/clients/_identifier_of_client's_account_
Headers	
Accept: application/json

Authorization: Bearer {token}


Returned answer:

{
   "id":"_client_api_id_",
   "timezone":"_client's_timezone_",
   "wallet":{
      "balance":_state_of_MG_wallet_,
      "credit":_overdraft_amount_,
      "income":_total_replenish_sum_,
      "currency":"_client_currency_"
   }
}
All refunds are made in cents (0.01$) balance can have both positive and negative value. Available funds are defined as: balance + credit. Funds spent on advertising: income balance.

Getting a collection of client's source filters
Method	GET
URL	api.mgid.com/v1/clients/_identifier_of_client's_account_/sources-blocklist
Headers	
Accept: application/json

Authorization: Bearer {token}

Request example:

api.mgid.com/v1/clients/{client id}/sources-blocklist

Returned answer:

{
    "id": _client_id_,
    "sourceFilters": {
        "filterType": "blocklist",
        "sources": [
            "Homepage Lifestyle",
            "Homepage News",
            "domain.com",
            "domain2.com"
        ],
        "sourcesIds": [
            1088,
            1089,
            10001,
            10002
        ]
    }
}
Filter type - blocklist, off (off - no data)

 

Setting filters on an account level
Affects all client's campaigns using sources optimization

Method	PATCH
URL	api.mgid.com/v1/clients/_identifier_of_client's_account_/?sourceFilters=editing_method, filter_type, sourceId1, source2
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters (required parameters are marked with asterisk *):

Parameter	Values
sourceFilters*	
Only for campaigns with sources optimization enabled

Can be passed source ID SourceId1, SourceId2, etc. or source name, such as source, source1, etc.

editing_method, filter_type, sourceId1, source2...

Request example:

api.mgid.com/v1/clients/{client id}?sourceFilters=include,blocklist,domain1.com,domain2.com
Editing methods:

include — enables the source.
exclude — disables the source.
Filter types:

blocklist — applies a blocklist to the sources.
off — turns off the filter for the sources.
Returned answer:

{
   "msg":"success",
}
Error - nonexistent source IDs or names or invalid sources (e.g., non-integer or incorrect format):

{"errors":["[SOURCES_DO_NOT_EXIST]"]}
Error - sources are not passed:

{"errors":["[SOURCES_CANNOT_BE_EMPTY]"]}
Error - invalid filter method (include | exclude) or missing parameters:

{"errors":["[ERROR_NOT_VALID_METHOD]"]}
Error - invalid filter type or missing parameters:

{"errors":["[ERROR_NOT_VALID_FILTER_TYPE]"]}
 

Working with client's advertising campaigns
 

Getting a collection of client's advertising campaigns
Method	GET
URL	api.mgid.com/v1/goodhits/clients/_client's_accont_ID_ / campaigns[_ad_campaign_ID_]
Headers	
Accept: application/json

Authorization: Bearer {token}

If _ad_campaign_ID_ was not passed, then the method returns a collection of client's advertising campaigns. If the ID has been passed correctly, it returns information only about specific ad campaign.

Sometimes requests fail if a campaign returns too much data. Reduce the limit and/or request only the fields you need.


Transferred parameters (required parameters are marked with asterisk *):

Parameter	Value
Fields	
array of client's properties, information on which you
need to get.( example: fields=['name','ipsFilter','domainsFilter']).  
If the parameter is not passed, then all properties are returned. The list may include the following properties:
id - ad campaign id
language - ad campaign language id
name - ad campaign id  
status - ad campaign status
ipsFilter- IP filter settings  
domainsFilter - domain filter settings  
widgetsFilterUid - widget filter settings
limitsFilter — limit settings for budget and clicks
targets - ad campaign operating systems targeting
languageTargeting - language filter settings. Ad campaign language id
browserTargeting - browsers filter settings. Possible browser values
category - campaign category ID
sourcesOptimization - Sources Optimization settings
sourceFilters - sources added to the blocklist at the campaign and account levels. Only for campaigns with sources optimization enabled.
whenAdd - date of campaign creation
campaignType - campaign type
statistics - clicks and wages
trackingOptions - utm tags and values
searchFeedProviderId - ID of search feed provider (search feed campaigns only)
limit	turns on the pagination, limiting the number of campaigns displayed on the page.
start	uses for navigation for pagination pages. The default is 0.
 

Languages list:

ID	NAME	LANGUAGE_CODE
1	English	en
2	Spanish	es
3	French	fr
4	German	de
5	Vietnamese	vi
6	Dutch	nl
7	Italian	it
8	Portuguese	pt
9	Indonesian	id
10	Greek	el
11	Thai	th
12	Hindi	hi
13	Khmer	km
14	Swedish	sv
15	Hungarian	hu
16	Malay	ms
17	Romanian	ro
18	Norwegian	no
19	Croatian	hr
20	Polish	pl
21	Finnish	fi
22	Danish	da
23	Filipino	fil
24	Czech	cs
25	Korean	ko
26	Bosnian	bs
27	Slovak	sk
28	Japanese	ja
29	Bulgarian	bg
30	Slovene	sl
31	Macedonian	mk
32	Turkish	tr
33	Estonian	et
34	Armenian	hy
35	Serbian	sr
36	Lithuanian	lt
37	Azerbaijani	az
38	Latvian	lv
39	Russian	ru
40	Urdu	ur
41	Arabic	ar
42	Hebrew	he
43	Chinese	zh
44	Georgian	ka
45	Nepali	ne
46	Albanian	sq
47	Bengali	bn
48	Sinhalese	si
49	Uzbek	uz
50	Ukrainian	uk
51	Tamil	ta
52	Telugu	te
53	Persian	fa
54	Somali	so
55	Tajik	tg
56	Kyrgyz	ky
57	Lao	lo
58	Gujarati	gu
59	Marathi	mr
60	Malayalam	ml
61	Kannada	kn
62	Burmese	my
63	Kazakh	kk
64	Turkmen	tk
65	Afrikaans	af
66	Punjabi	pa
67	Belarusian	be
68	Swahili	sw
69	Mongolian	mn
70	Amharic	am
72	Catalan	ca
96	Tagalog	tl
104	Odia	or
Answer returned:

{
   "_advertising_campaign_id_":{
      "id":_advertising_campaign_id_,
      "language":_campaign_language_,
      "name":"_advertising_campaign_name_",
      "status":{
         "id":_state_identifier_,
         "name":"_ad_campaign_status_name_",
         "reason":"_campaign_state"
      },
      "domainsFilter":{
         "filterType":"_domain_filter_type_",
         "domainsNames":[
            "_domain_1_",
            "_domain_2_",
            . . . . . . .
         ]
      },
      "ipsFilter":{
         "filterType":"_IP_filter_type_",
         "ips":[
            "IP_adress_1",
            "IP_adress_2",
            . . . . . .
         ]
      },
      "widgetsFilterUid":{
         "filterType":"_widget_filter_type_",
         "widgets":{
            " _widget_id_1":"[_widget_subid_1]",
            " _widget_id_2":"[_widget_subid_2]",
            " _widget_id_3":"[ _widget_subid_3]",

         }
      },
      "statistics":{
         "clicks":_counted_clicks_amount_for_today_,
         "wages":_funds_spent_for_today_
      },
      "category":{
         "id":"_category_ID_", 
         "name":"_category_name_"
      },
      "startDate": "YYYY-MM-DD",
      "endDate": null,
      },
      "sourceFilters": {
        "filterType": "blocklist",
        "sources": [
            "domain.com"
        ],
        "sourcesIds": [
            4114
        ]
      }
   },
   ...........
}
Possible errors in this section:

[ERROR_TOO_MANY_CAMPAIGNS_USE_PARAMS_LIMIT_AND_START] - if the user has more than 500 campaigns and the optional limit parameter is not specified
[ERROR_MAX_LIMIT_PER_PAGE_500] - if the additional parameter limit is specified and it is more than 500
Status property indicates current campaign state and status.

Description of status value returned:

id

Description

1

Campaign is blocked due to end date

2

Campaign has reached total budget limit

3

Campaign has reached total clicks limit

4

Campaign is blocked by manager of client

5

Campaign is blocked due to negative balance

6

Campaign is unlimited and active

7

Campaign hasn't reached its daily limit

8

Yesterday campaign has reached its daily clicks or budget limit and is active

9

Campaign has reached its daily budget limit

10

Campaign has reached its daily clicks limit

11

Campaign is paused due to time schedule settings

12

Campaign stopped because the client delayed
13	Campaign stopped by the manager
14	Campaign deleted
15	Campaign stopped because the client declined to proceed and rejected it
19	Campaign stopped due to a violation of the creativity rules
IpsFilter property displays the IP filter settings of an advertising campaign (teasers of this campaign should not be shown to visitors with this IP). _IP_filter_type_ can take the following values:
● off - the filter is disabled
● except - "except" filter  
● ips - a list of IP address ranges for filtering as an array.  _spent_by_the_client_for_today_ in $

 

Getting advertising campaign statistics by site
Method	GET
URL	api.mgid.com/v1/goodhits/campaigns/_ad_campaign_ID_/quality-analysis/_uid_
Headers	
Accept: application/json

Authorization: Bearer {token}

Transfered parameters (required parameters marked with asterisk *):

Parameters	Values
campaignId*	_ad_campaign_ID_
dateInterval	
Period for which you need to get statistics. If interval is not specified, returns statistics for 90 days. Valid values are:

interval - need to 2 specify additional parameters: startDate and endDate in format yyyy-mm-dd
all - all time
thisWeek - current week
lastWeek - last week
thisMonth - current month
lastMonth - last month
lastSeven - last 7 days
today - today
yesterday - yesterday
last30Days - last 30 days
uid	_uid_. If specified, displays information only for this site.
browser	Filters data by browser. 1 value to a parameter can be passed. Browsers values list
os	Filters data by OS. 1 value to a parameter can be passed. OS codes list
country	Filters data by country. 1 value to a parameter can be passed. Countries codes list
Request example:

api.mgid.com/v1/goodhits/campaigns/campaign_id/quality-analysis/uid?dateInterval=lastMonth&browser=chrome&os=android10mobile&country=CA
 

Answer returned:

{  
 "_campaignId_":{
  "_dateInterval_":{  
     "_widgetUid_":{  
        "clicks":"_clicks_",
        "spent":"_spent_",
        "cpc":"_cpc_client_currency_",
        "qualityFactor": "_quality_factor_",
        "buy":"_conversions_at_the_buying_stage_",
        "buyCost":"_price_of_conversions_at_the_buying_stage_",
        "decision":"_conversions_at_the_decision_stage_",
        "decisionCost":"_price_of_conversions_at_the_decision_stage_",
        "interest":"_conversions_at_the_interest_stage_",
        "interestCost":"_price_of_conversions_at_the_interest_stage_",
        "sources": {
            "17": {
                   "clicks":"_clicks_",
                   "spent":"_spent_",
                   "cpc":"_cpc_client_currency_",
                   "qualityFactor": "_quality_factor_",
                   "buy":"_conversions_at_the_buying_stage_",
                   "buyCost":"_price_of_conversions_at_the_buying_stage_",
                   "decision":"_conversions_at_the_decision_stage_",
                   "decisionCost":"_price_of_conversions_at_the_decision_stage_",
                   "interest":"_conversions_at_the_interest_stage_",
                   "interestCost":"_price_of_conversions_at_the_interest_stage_",
            },
            "0": {
                  "clicks":"_clicks_",
                  "spent":"_spent_",
                  "cpc":"_cpc_client_currency_",
                  "qualityFactor": "_quality_factor_",
                  "buy":"_conversions_at_the_buying_stage_",
                  "buyCost":"_price_of_conversions_at_the_buying_stage_",
                  "decision":"_conversions_at_the_decision_stage_",
                  "decisionCost":"_price_of_conversions_at_the_decision_stage_",
                  "interest":"_conversions_at_the_interest_stage_",
                  "interestCost":"_price_of_conversions_at_the_interest_stage_",
            }
        }
     }
  }
}
If there are some errors:

{"errors":["[_error_]"]}
[WIDGETS_WITH_THESE_IDS_DO_NOT_EXIST] - widgets with given uid do not exist, if there are valid uid in the list - they will be written to the database

[ERROR_INVALID_OS_TARGETING] - invalid os value has been specified
[ERROR_INVALID_BROWSER_TARGETING] - invalid browser value has been specified
[ERROR_INVALID_COUNTRY_TARGETING] - invalid country value has been specified

{
"id":_campaignId_, 
"errors":"[WIDGETS_WITH_THESE_IDS_DO_NOT_EXIST]",
"data":["1000000","111111"]
}
Getting advertising campaign statistics by source
Method	GET
URL	api.mgid.com/v1/goodhits/campaigns/_ad_campaign_ID_/quality-analysis-sources/
Headers	
Accept: application/json

Authorization: Bearer {token}

Transfered parameters (required parameters marked with asterisk *):

Parameters	Values
campaignId*	_ad_campaign_ID_
dateInterval	
Period for which you need to get statistics. If an interval is not specified, returns statistics for 90 days. Valid values are:

interval - need to 2 specify additional parameters: startDate and endDate in format yyyy-mm-dd
all - all time
thisWeek - current week
lastWeek - last week
thisMonth - current month
lastMonth - last month
lastSeven - last 7 days
today - today
yesterday - yesterday
last30Days - last 30 days
source	The source parameter can be specified by the ID or name of the source
Request example:

api.mgid.com/v1/goodhits/campaigns/campaign_id/quality-analysis-sources/?dateInterval=interval&startDate=2024-10-27&endDate=2024-10-29&source=Somesource+-+iOS&widgetId=ON
Answer returned:

{
    "_campaign_ID_": {
        "2024-11-16_2024-11-16": {
            "20001": {
                "sourceName": "domain.com",
                "sourceId": 100001,
                "clicks": 0,
                "adRequests": 0,
                "impressions": 0,
                "viewability": 0,
                "spent": 0,
                "dataFee": 0,
                "cpcWithoutDataFee": 0.573333,
                "ctr": 0,
                "cpc": 0.573333,
                "cpm": 0,
                "conversionsRateInterest": 0,
                "conversionsRateDecision": 0,
                "conversionsRateBuy": 0,
                "conversionsCostInterest": 0,
                "conversionsCostDecision": 0,
                "conversionsCostBuy": 0,
                "revenue": 0,
                "profit": 0,
                "roas": 0,
                "epc": 0,
                "vCpm": 0,
                "vCtr": 0,
                "etr": 0,
                "winRate": 96.22,
                "conversionsInterest": 0,
                "conversionsDecision": 0,
                "conversionsBuy": 0,
                "toggle": true,
                "canChangeToggle": true,
                "qualityFactor": 1.3,
                "qualityFactorUpdatedAt": "01.11.2024 01:56:01",
                "previousQualityFactor": 0.11,
                "isBlocked": false
            }
        }
    }
}
If an ID that does not belong to a sources optimization campaign, return the error: 

[ERROR_CAMPAIGN_IS_NOT_TRANSPARENCY]
If a nonexistent source ID or name is provided, or if the parameter is empty, return the error: 

[ERROR_SOURCES_DO_NOT_EXIST]
If an invalid parameter is provided, return the error: 

[ERROR_NOT_VALID_parameter_name]
 

 

Advertising campaigns detailed daily statistics
Method	GET
URL	api.mgid.com/v1/goodhits/campaigns/_adcampaign_id_/statistics
Headers	
Accept: application/json

Authorization: Bearer {token}


Transferred parameters (required parameters are marked with asterisk *):

Parameters	Value
type*	Statistics type. Values:  byClicksDetailed
date*	Format date: YYYY-MM-DD

Returned values:
If the request is correctly, it returns an array of data in the next format:

{
   "id":_ad_campaign_ID_,
   "statistics":{
      "summary":{
         "numberOfClicks":_total_number_of_clicks_,
         "numberOfAcceptedClicks":_ enrollment_clicks _,
         "fundsEarned":_spent_clicks _,
         "numberOfRejectedClicks":_not_couted_clicks_,
         "numberOfShows":_total_number_of_shows_
      },
      "acceptedClicks":[
         {
            "time":"_click_time_",
            "ip":"_ip_address_",
            "referer":"_referrer_",
            "teaserId":"_id_teaser_",
            "sourceId":"_source_id_",
            "source":"_source_"
            "informerUid":"_informer_uid_",
            "country":"_two_letter_country_code",
            "region":"_region_",
            "price":"_click_price_"
         },
         ….
      ]
   }
}
Advertising campaigns daily statistics
Method	GET
URL	api.mgid.com/v1/goodhits/clients/{clientId}/campaigns-stat
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters:

Parameter	Value
dateInterval	
Period for which you need to get statistics. If interval is not specified, returns statistics for 90 days. Valid values are:

interval - need to 2 specify additional parameters: startDate and endDate in format yyyy-mm-dd
all - all time
thisWeek - current week
lastWeek - last week
thisMonth - current month
lastMonth - last month
lastSeven - last 7 days
today - today
yesterday - yesterday
last30Days - last 30 days
Answer:

"_campaign_id_":{
   "campaign_id":_campaign_id_,
   "imps":_imps_,
   "clicks":_clicks_,
   "spent":_spent_,
   "avcpc":_average_cpc_
}
If the customer has conversion settings - additional data transferred:

buy - quantity of buying conversions
buyCost - cost of buying
decision - quantity of decision conversions
decisionCost - cost of decision
interest - quantity of interest conversions
interestCost - cost of interest
convertionCost - conversions profit
revenue - revenue
epc - earn per click
profit - revenue - spent
If there are some errors:

{"errors":["[_error_]"]}
[THERE_NO_DATA_IN_CHOSEN_PERIOD] - if there is no data in chosen period

[INVALID_VALUE_FOR_INTERVAL] - invalid value for interval

Advertising campaigns daily statistics for video campaigns
Method	GET
URL	api.mgid.com/v1/goodhits/clients/{clientId}/campaigns-video-stat
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters:

Parameter	Value
dateInterval	
Period for which you need to get statistics. If interval is not specified, returns statistics for 90 days. Valid values are:

interval - need to 2 specify additional parameters: startDate and endDate in format yyyy-mm-dd
all - all time
thisWeek - current week
lastWeek - last week
thisMonth - current month
lastMonth - last month
lastSeven - last 7 days
today - today
yesterday - yesterday
last30Days - last 30 days
Answer:

 "_campaignId_":{
    "campaignId":_campaign_id_,
    "impressions":_impressions_,
    "viewability":_viewability_,
    "first_quartile":_first_quartile_,
    "midpoint":_midpoint_,
    "third_quartile":_third_quartile_,
    "complete":_complete_,
    "completion_rate":_completion_rate_,
    "clicks":_clicks_,
    "ctr":_ctr_,
    "spent":_spent_,
    "cpm":_cpm_
}
If there are some errors:

{"errors":["[_error_]"]}
[THERE_NO_DATA_IN_CHOSEN_PERIOD] - if there is no data in chosen period

[INVALID_VALUE_FOR_INTERVAL] - invalid value for interval

 

Creating a new ad campaign (with all settings)
Method	POST
URL	api.mgid.com/v1/goodhits/clients/_client_ID_/campaigns
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters (* - required; ** - required, if parent parameter transferred):

Section 1

Parameters	Value
name*	Campaign name. Must be unique for the client. 128 symbols max.
enabledGeoTargetingFlag*	Flag on/off GeoTargeting
keyword	Keyword.Required parameter for search_feed campaigns type 
geoTargets**	
List of countries and cities (regions) for targeting. Example:

{'method':'set','cities':['2'],'countries':['ua']}

If both cities and countries are filled, the priority will be given to the 'countries' parameter.

startDate	Campaign start date YYYY-MM-DD
language	ad campaign language_code
languageTargets	Filter by language_code of an ad campaign in include mode. IDs of languages separated by a comma.
campaignType	product/content/push/search_feed. If campaign_type didn't transfer campaign_type = product
advertiserName*	Advertiser name. Field length 1-25 characters
categoryId	campaign category ID
sourcesOptimization	If set to "true" enables the "Sources Optimization" feature in the campaign. If the parameter is not provided, the system default value is "false."
searchFeedProviderId	ID of search feed provider (search feed campaigns only)
Possible errors for this section:

[ADVERTISE_NAME_EXISTS]
[CAMPAIGN_NAME_TOO_LONG]
[ERROR_PARAMETER_ENABLED_GEO_TARGETING_FLAG_CAN_NOT_BE_EMPTY]
[ERROR_PARAMETER_GEO_TARGETS_CAN_NOT_BE_EMPTY]
[ERROR_INVALID_PARAMETER]
[ERROR_WRONG_DATE_FORMAT]
[ERROR_NOT_VALID_CAMPAIGN_TYPE]
[ERROR_PARAMETER_LANGUAGE_TARGETS_VALUE_INVALID]
[ERROR_PARAMETER_LANGUAGE_TARGETS_EMPTY]
[NOT_VALID_WHEN_AUTOSTART] - startDate < today's date
 

Section 2
If at least one of the utm_source, utm_campaign, utm_medium transferred, then all three are required
Parameters	Value
utm_source**	
0 9, A Z, a z, -, _, =, +, &, @, /, :, ^,.

 (up to 200 symbols)
utm_campaign**	
0 9, A Z, a z, -, _, =, +, &, @, /, :, ^,.

(up to 200 symbols)

utm_medium**	
0 9, A Z, a z, -, _, =, +, &, @, /, :, ^,.

(up to 200 symbols)

utm_custom	
Macroses:

{widget_id}, {source}, {source_id}, {teaser_id}, {campaign_id}, {category_id}, {user_id}, {geo}, {geo_region}, {ifa}, {gdpr}, {gdpr_consent}, {click_id}, {click_price}, {client_id}, {title}, {referrer}

Possible errors for this section:

[UTM_TAGGING_FIELDS_MUST_NOT_BE_EMPTY]
[UTM_CUSTOM_TOO_LONG_STR]
[WRONG_UTM_CUSTOM_FORMAT]
[UTM_MEDIUM_TOO_LONG_STR]
[UTM_SOURCE_TOO_LONG_STR]
[UTM_CAMPAIGN_TOO_LONG_STR]
 

Section 3
If limitType parameter transferred, then limit type must be specified (day or total)
Parameters	Value
limitType	
clicks_limits - limit on clicks, budget_limits - limit on budget

dailyLimit**	
Setting the limit per day.

For clicks_limits  must be an integer value. Min 500. If a value is empty - campaign has no limits.

For budget_limits  The value of 2 characters after the decimal point (up to hundredths).

overallLimit**	
Setting the limit on the campaign in general.

For clicks_limits – must be an integer value and more than a dailyLimit, if specified. If value is empty - campaign has no limits.

For budget_limits value with 2 characters after the decimal point (up to hundredths). Must be more than a dailyLimit, if specified. If value is empty - campaign has no limits.

splitDailyLimitEvenly	Option of evenly daily traffic distribution. 0 - off, 1 - on.
Possible errors for this section:

[NOT_ENOUGH_PARAMETERS]
[ERROR_NOT_VALID_TYPE]
[ERROR_GREATER_THAN_LIMIT_PER_DAY]
[MINIMAL_DAILY_BUDGET_LIMIT_ERROR]
[WRONG_USE_FLOATING_LIMIT]
[ERROR_SPLIT_DAILY_LIMIT_EVENLY_IS_AVAILABLE_IF_ONLY_DAILY_LIMIT_SET]
[ERROR_MINIMAL_DAILY_CLICKS_LIMIT_IS_ %]
[ERROR_MINIMAL_DAILY_BUDGET_LIMIT_IS_ %]
[ERROR_OVERALL_CLICKS_LIMIT_LESS_THAN_DAILY_LIMIT]
[ERROR_OVERALL_BUDGET_LIMIT_LESS_THAN_DAILY_LIMIT]
 

Section 4

Parameters	Value
browserTargets	_browser1_, _browser2_, _browser3_
osTargets	_os1_,_os2_,_os3_
Possible errors for this section:

"[ERROR_NO_ENOUGH_PARAMETERS]"
Answer returned:

{
     "id":_campaign_id_,
}
 

Creating a new ad campaign
Method	POST
URL	api.mgid.com/v1/goodhits/clients/_client_ID_/campaigns
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters (required parameters are marked with asterisk *):

Parameters	Values
name*	Campaign name. Must be unique for the client
enabledGeoTargetingFlag*	Flag on/off GeoTargeting
keyword	Keyword.Required parameter for search_feed campaigns type 
geoTargets
List of countries and cities (regions) for
(parameter is required if targeting:
enabledGeoTargetingFlag =1)	
{'method':'set','cities':['2'],'countries':['ua']}

If both cities and countries are filled, the priority will be given to the 'countries' parameter.

language	ad campaign language_code
languageTargets	Filter by language_code of an ad campaign in include mode. IDs of languages separated by a comma.
startDate	campaign start date YYYY-MM-DD
endDate	campaign end date YYYY-MM-DD
campaignType	product/content/push/search_feed. If parameter didn't send campaign_type = product
advertiserName*	Advertiser name. Field length 1-25 characters
categoryId	campaign category ID
sourcesOptimization	If set to "true" enables the "Sources Optimization" feature in the campaign. If the parameter is not provided, the system default value is "false."
Answer returned:

{
  "id":_campaign_ID_,
}
If there already exists an ad campaign with the name specified in the request, then new campaign will not be created and system return error:

{
"errors":
[ "[ADVERTISE_NAME_EXISTS]" ]
}
 

UTM markup settings for ad campaign
Method	PUT
URL	api.mgid.com/v1/goodhits/campaigns/_campaign_ID_/utmtracking/
Headers	Accept: application/json
Authorization: Bearer {token}
Transferred parameters:

Parameters	Value
utm_source	Standard setting Google Analytics to track traffic source
utm_campaign	Standard setting Google Analytics to track purchases traffic campaign
utm_medium	Standard setting Google Analytics to track traffic channel
utm_custom	Custom markup. Ability to specify custom settings, which
will be added to the links campaign teaser
Values for Google Analytics (utm_source, utm_campaign, utm_medium) must be given a single query. If you are using one of the this parameters, other are required. Error if one of values is empty: [UTM_TAGGING_FIELDS_MUST_NOT_BE_EMPTY]  
When you specify the default settings Google Analytics also automatically added utm_content and utm_term . In tag utm_content  automatically substituded ID ads.  utm_term=_site_ID_

Utm_custom , should not exceed 200 characters, or system return error:  [UTM_CUSTOM_TOO_LONG_STR]  

Valid characters are: 0, 9, A Z, a z, -, _, =, +, &, @, /, :, ^,. . And macros: {widget_id}, {source}, {source_id}, {teaser_id}, {campaign_id}, {category_id}, {user_id}, {geo}, {geo_region}, {ifa}, {gdpr}, {gdpr_consent}, {click_id}, {click_price}, {client_id}, {title}, {referrer}.  

Or system return error:  [WRONG_UTM_CUSTOM_FORMAT]

You can't use system parameters adclid or  adclida - you'll get an error [ERROR_MGCLID_MGCLIDA_SYSTEM_PARAMETERS_CANNOT_USE_THEM]


If you pass an empty field markup is disabled. If the settings are saved successfully, system return campaign ID:

{
  "id":_campaign_ID_
}
 

Setting limits on advertising campaign
Method	PATCH
URL	api.mgid.com/v1/goodhits/clients/_client_ID_/campaigns/_campaign_ID_
Headers	
Accept: application/json

Authorization: Bearer {token}


Transferred parameters send in the body of the request (required parameters marked with asterisk *):

Parameters	Value
limitType*	
clicks_limits - clicks limit

budget_limits - budget limit

dailyLimit	
Setting the limit per day.

For clicks_limits  must be an integer value. Min 500. If a value is empty - campaign have no limits.

For budget_limits  The value of 2 characters after the decimal point (up to hundredths).

overallLimit	
Setting the limit on the pampaign in general.

For clicks_limits – must be an integer value and more than a dailyLimit, if specified. If value is empty - campaign have no limits.

For budget_limits value with 2 characters after the decimal point (up to hundredths). Must be more than a dailyLimit, if specified. If value is empty - campaign have no limits.

splitDailyLimitEvenly

Option of evenly daily traffic distribution. 0 - off, 1 - on

The minimal daily budget limit depends on the currency and campaign type
The total limit can not be less than the daily limit
Step limit - 1 cent
A system returns  _campaign_ID_ if  all done:

{
  "id":_campaign_ID_
}
 


Block / unblock advertising campaign
Method	PATCH
URL	api.mgid.com/v1/goodhits/clients/_client_ID_/campaigns/_campaign_ ID_
Headers	
Accept: application/json

Authorization: Bearer {token}


Transferred parameters send in the body of the request:

Parameters	Value
whetherToBlockByClient	0 – unlock ad campaign
1 — lock ad campaign
 

Getting creation date of ad campaign
Method	GET
URL	api.mgid.com/v1/goodhits/clients/_client's_accont_ID_/campaigns/_ad_campaign_ID_?fields=['whenAdd']
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters:

Parameter	Value
fields	whenAdd
Answer returned:

{
 "id":_ad_campaign_ID_,
 "whenAdd":_campaigns_creation_date_
}
 

Setting the coefficient of a selective auction of an advertising campaign
Method	PATCH
URL	api.mgid.com/v1/goodhits/clients/_clientID_/campaigns/_campaignID_
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters send in the body of the request (required parameters marked with asterisk *):

Parameters	Values
qualityFactor*	
Required only for campaigns with sources optimization disabled

Contains a widgetUID and a new quality factor on the site. There can be several pairs in json format: {"_widgetUid1_":_qf1_,"_widgetUid2_s_sourceId2_":_qf2_,"_widgetUid3_":_qf3_}

sourceQualityFactor*	
Required only for campaigns with sources optimization enabled

Contains the source name or ID and a new CPC multiplier for each source. There can be several pairs in json format:

{"source1": "qf1","source2": "qf2","source3": "qf3"}
or {"sourceId1": "qf1","sourceId2": "qf2","sourceId3": "qf3"}

Answer returned:

{  
 "id":_ad_campaign_ID_"
}
Possible errors:

ERROR_CAMPAIGN_IS_DSP_CANT_CHANGE_QF- DSP campaign
ERROR_QUALITY_FACTOR_INVALID_FORMAT - wrong data format in parameter qualityFactor
ERROR_WIDGETUID_INVALID_FORMAT - wrong data format in parameter _widgetUid2_or _widgetUid2_s_sourceId2_
WIDGETS OPTIMIZATION IS NOT AVAILABLE FOR THIS CAMPAIGN. THIS CAMPAIGN IS ALREADY USING SOURCES OPTIMIZATION - when users attempt to modify settings via old routes for campaign using sources optimization
ERROR_CAMPAIGN_IS_NOT_TRANSPARENCY_CANT_CHANGE_QF - isn't a transparency campaign
ERROR_SOURCE_INVALID_FORMAT - wrong data format in parameter sourceName or sourceId
 

Setting the coefficient of a selective auction to all sub-sources
Method	PATCH
URL	api.mgid.com/v1/goodhits/clients/_clientID_/campaigns/_campaignID_
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters send in the body of the request (required parameters marked with asterisk *):

Parameters	Values
widgetQualityFactor*	It contains a widgetUID and a new quality factor. Applies a source value to all its sub-sources. There can be several pairs in json format: {"_widgetUid1_":_qf1_,"_widgetUid2_":_qf2_,"_widgetUid3_":_qf3_}
Answer returned:

{  
 "id":_ad_campaign_ID_"
}
Possible errors:

ERROR_CAMPAIGN_IS_DSP_CANT_CHANGE_QF- DSP campaign
ERROR_WIDGET_QUALITY_FACTOR_INVALID_FORMAT - wrong data format in parameter widgetQualityFactor
ERROR_WIDGETUID_INVALID_FORMAT - wrong data format in parameter _widgetUid2_
WIDGETS OPTIMIZATION IS NOT AVAILABLE FOR THIS CAMPAIGN. THIS CAMPAIGN IS ALREADY USING SOURCES OPTIMIZATION - when users attempt to modify settings via old routes for campaign using sources optimization
Retrieving conversion targets for a client
Method	GET
URL	
api.mgid.com/v1/goodhits/clients/_client_ID_/conversions-targets

Headers	
Accept: application/json

Authorization: Bearer {token}

Response:

{
    "stages": {
        "decision": {
            "cpa": 3.99,
            "unique": true,
            "targetType": "url",
            "categoryId": 5,
            "condition":{
                "type":"contain",
                "value":"testerovich"
            }
        },
        "interest": {
            "cpa": 2.34,
            "unique": true,
            "targetType": "url",
            "categoryId": 4,
            "condition":{
                "type":"contain",
                "value":"testerovich2"
            }
        }
    }
}
 

Retrieving conversion settings for an advertising campaign
Method	GET
URL	api.mgid.com/v1/goodhits/campaigns/_campaign_ID_/conversions
Headers	
Accept: application/json

Authorization: Bearer {token}

The response comes with an array of conversion settings for an advertising campaign.

The array can be:

empty (there are no settings)
with three elements (all conversion stages with settings)
from one to three elements (only a part of the stages is configured)
Each element will contain the following information:

stage - name of the conversion stage
target_id - The ID of an existing target that is associated with the specified stage.
type - type of conversion. The options are: 'url', 'event', 'visited', 'regexp' and 'postback'.
conditions - conversion trigger settings.
conditions.[i].type - type of trigger condition. The options are 'contain', 'starts', 'ends', 'visited', 'regexp' and 'postback'.
conditions.[i].value - value of trigger condition.
price - cost per conversion in the client's currency. Either the price will be a number, or 0 if no price is specified.
Response:

[
    {
        "stage": _stage_,
        "target_id": _target_id_,
        "type": _target_type_,
        "conditions": [
            {
                "type": _confition_type1_,
                "value": _condition_value1_
            },
            {
                "type": _confition_type2_,
                "value": _condition_value2_
            }
        ],
        "price": _price_of_conversion_
    },
    ...
]
Response with buy stage:

[
    {
        "stage": "buy",
        "target_id": 59041,
        "type": "url",
        "conditions": [
            {
                "type": "contain",
                "value": "thankyou.php"
            }
        ],
        "price": 123.123457
    }
]
Creating conversion targets for an advertising campaign
Method	POST
URL	api.mgid.com/v1/goodhits/campaigns/_campaign_ID_/conversions
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters send in the body:

Parameter	Value
buy	settings for stage buy
decision	settings for stage decision
interest	settings for stage interest
Each stage has next values:

cpa: float;
unique: boolean;
targetType: url, event, postback;
categoryId: number;
ID: 1 (Registration)

ID: 7 (Add to Cart)

ID: 9 (Other)

ID: 10 (Page View)

ID: 11 (Contact)

ID: 12 (Lead Form Engagement)

ID: 13 (Lead Form Submission)

ID: 14 (Sign Up)

ID: 15 (Start Checkout)

ID: 16 (First Time Deposit)

ID: 17 (Order Placed)

ID: 18 (Purchase)

ID: 19 (AppInstall)

ID: 20 (Redirect Click)

condition type: starts, contain, ends;
condition value: string;
identifier: string (event name for event targetType)
Example:

{
    "stages": {
        "buy": {
            "cpa": 0.3,
            "name": "Test-Den3",
            "unique": true,
            "targetType": "url",
            "categoryId": "1",
            "condition": {
                "type": "ends",
                "value": "tesn001"
            },
            "identifier": "66"
        }
    }
}
Editing conversion settings for an advertising campaign
Method	PATCH
URL	api.mgid.com/v1/goodhits/campaigns/_campaign_ID_/conversions
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters send in the body:

Parameter	Value
buy	settings for stage buy
decision	settings for stage decision
interest	settings for stage interest
Value format: id: number (target_id); cpa: float; unique: boolean

_id_ - ID of an existing target (target_id)
_cpa_ - cpa in the client's currency. Either a number or null
_unique_ - marks stage as unique. Can be true or false
Example:

{
    "stages": {
        "buy": {
            "id": 2987,
            "cpa": 3.99,
            "unique": true
        },
        "interest": {
            "id": 753455,
            "cpa": 2.34,
            "unique": true
        }
    }
}
Response:

{
    "id":_campaign_id_
}
Possible errors:

[ERROR_NOT_VALID_CAMPAIGN_ID] - invalid campaign ID (zero or invalid ID)
[ERROR_CAMPAIGN_DOES_NOT_EXIST] - the campaign with this ID does not exist or belongs to another client
[ERROR_CAMPAIGN_HAS_ANOTHER_CONVERSIONS_DATA_SOURCE] - the campaign has a different source of conversions (GA, YM, or GTM)
[TARGET_ID_EMPTY] - target ID not passed
[CONVERSION_TARGET_UNIQUE_ERROR] - the same goal is used in several stages
[TARGET_ID_INVALID] - non-existent goal or purpose of another client

Delete conversion target
Method	DELETE
URL	api.mgid.com/v1/goodhits/campaigns/_campaign_ID_/conversions
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters:

Parameter	Value
stages	buy, decision, interest
Example:

{
    "stages": ["buy", "interest"]
}
Removing the campaign to trash
Only stopped ad campaigns can be removed.

Method	DELETE
URL	api.mgid.com/v1/goodhits/clients/_client_ID/campaigns/_ad_campaign_ID_
Headers	
Accept: application/json

Authorization: Bearer {token}

Answer returned:

{
    "id":_campaign_id_
}
Possible errors:

[ERROR_CAMPAIGN_DOES_NOT_EXIST] - Invalid campaign id

[ERROR_CAMPAIGN_DOES_NOT_EXIST] - Campaign does not belong to the client

[WRONG_CAMPAIGN_ID] - Campaign type video

 

Getting an available CTA for an advertiser's campaign
Method

GET
URL

api.mgid.com/v1/goodhits/campaigns/campaign_ID/call-to-actions
Headers

Accept: application/json

Authorization: Bearer {token}

The endpoint returns a list of available call-to-action options for the specified campaign.

Answer returned:

{ 
  "_call_to_action_", 
  ... 
}
 
Changing search feed provider for the existing search feed campaign
Method	
PATCH

URL	api.mgid.com/v1/goodhits/clients/client_ID/campaigns/campaign_ID
Headers	Accept: application/jsonAuthorization: Bearer {token}
Parameter	Value
searchFeedProviderId	ID - ID of the search provider, available only for search feed campaigns
List of search provider IDs

ID	Name
1	Tonic
2	Sedo
3	System1
4	ExploreAds
5	Visymo
6	Ads.com / Bodis
7	DomainActive / OBMedia
8	Codefuel / Perion
9	Inuvo
Added support for the searchFeedProviderId parameter in Search Feed campaigns.
The field is now available for retrieving, creating, and updating campaigns through the following API requests:

GET /v1/goodhits/clients/{client_api_id}/campaigns/{campaign_id}


POST /v1/goodhits/clients/{client_api_id}/campaigns?searchFeedProviderId={provider_id}


PATCH /v1/goodhits/clients/{client_api_id}/campaigns/{campaignId}?searchFeedProviderId={provider_id}
 

 

Advertising campaigns targeting settings
Setting up the geo targeting of advertising campaigns
Getting geotargeting settings ad campaign of client:

Method	GET
URL	api.mgid.com/v1/goodhits/campaigns/_campaign_ID_/targetings/geo
Headers	
Accept: application/json

Authorization: Bearer {token}

Answer returned:

{
   "targets":    {
      "actual":{
         "countries":{
            "_country_code_":{
               "code":"_ country_code _",
                "name":"_country_name_",
                "cities":[
                  "_city_ID_":{
                     "id":_ city_ID _,
                      "name":"_name_of_city",
                      "normalizedName":"_ Latin_letters_name _"                       
                  },
                  .......
               ]
            }            ......
         }
      },
      "requested":{
         "countries":{
            "_country_code_":{
               "code":"_country_code_",
                 "name":"_country_name_",
                 "cities":[
                  "_city_ID_":{
                     "id":_ city_ID _,
                       "name":"_ name_of_city_",
                       "normalizedName":"_ Latin_letters_name_"
                  },
                  .......
               ]
            }
         }
      }
   }
}
Section "actual"  contains the current geotargeting.  Section "request"  updated geotargeting settings that will be applied (or in the near future, or from the following day). If geotargeting settings are not used, it returns an answer like:

{
   "targets":{
      "actual":{
         "countries":[

         ]
      },
      "requested":{
         "countries":[

         ]
      }
   }
}
 

Getting a list of available countries for setting up geo targeting
Method	GET
URL	api.mgid.com/v1/dictionaries/geo
Headers	
Accept: application/json

Authorization: Bearer {token}


Transferred parameters (required parameters marked with asterisk *)::

Parameter	Value
type*	countries
Returns an array of countries that can be used for setting geotargeting:

[
   {
      "code":"_ two_letter_country_code _",
      "name":"_country_name_"
   },
   .....
]
 

Getting a list of available regions (cities) for geo targeting settings
Method	GET
URL	api.mgid.com/v1/dictionaries/geo
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters (required parameters marked with asterisk *)::

Parameters	Value	Comments
type*	cities	 
countries*	['_ two_letter_country_code _', ....]	An array of country codes for which you need to get a cities (regions) list.

Returns an array of regions (cities) that can be used for geo targeting:

[
   {
      "id":_city_ID_,
      "name":"_city_name_",
      "normalizedName":"_ name of city_Latin_Letters _",
      "countryCode":"_ two_letter_country_code _"
   },
   ......
]
 

Editing geo targeting settings for advertising campaign
Method	PUT
URL	api.mgid.com/v1/goodhits/campaigns/_campain_ID_/targetings/geo
Headers	
Accept: application/json

Authorization: Bearer {token}


Transferred parameters (required parameters marked with asterisk *)::

Parameter	Value
targets*	The list of countries and cities (regions) for targeting:
{ 'method':'set', 'cities': [ _city_ID_, . . . . . ], 'countries': [ two_letter_country_code _,  . . . . . . ] }If filled cities and countries in the priority will be countries parameter.
enabledFlag*	Flag on/off geo targeting(1/0)

If the request is correct, will be returned  ID edited ad campaign:

{
 "id":_campaign_ID_
}
If you do not specify any parameters or configured incorrectly, the changes  
settings will not be saved and will return an error message:

{
   "errors":[
      "[ERROR_NO_ENOUGH_PARAMETERS]"
   ]
}
 

Editing advertising campaign browser targeting
Method	PUT
URL	api.mgid.com/v1/goodhits/campaigns/_ad_campaign_ID_/targetings/browsers
Headers	
Accept: application/json

Authorization: Bearer {token}


Transferred parameters (required parameters marked with asterisk *)::

Parameter	Value
targets*	_ editing_method_ , _ browser_,_ browser_.....
enabledFlag*	0 – target off, 1 — target on
Possible values for the  _editing_method_ :
include- inclusion of a browser in the list for targeting

Possible values for _browser_ :

Name	Value
Other	others
Google Chrome	chrome
Safari	safari
Opera Mini	operamini
Opera Mobile	operamobile
Opera	opera
Firefox	firefox
MSIE	msie
Facebook	facebook
WebView	webview
Yandex Browser	yandex
Microsoft Edge	edge
UC Browser	ucbrowser
Pinterest App	pinterest
Mobile Samsung Brows	mobilesamsungbrowser
Google Search App	googlesearchapp
TopBuzz App	topbuzzapp
ViVo Browser	vivobrowser
Phoenix Browser	phoenixbrowser
Upon successful saving settings system returns campaign ID:

{
 "id":_campaign_ID_
}
 

Editing advertising campaign IP targeting   
Method	PATCH
URL	api.mgid.com/v1/goodhits/clients/_client_ID_/campaigns/_ad_campain_ID_
Headers	
Accept: application/json

Authorization: Bearer {token}


Transferred parameters send in the body of the request (required parameters marked with asterisk *):

Parameter	Value
ipsFilter*	_ editing_methods _ , _filter_type_, IP1,IP2....

Settings:

Editing methods:
include include an address in the list
exclude remove an address from the list
Filter type :
except  
only
off – filter off
IP can be specified as single or as subnets (192.168.0.1/24)

Upon successful saving settings system returns campaign ID:

{
 "id":_campaign_ID_
}
 

Editing advertising campaign operating system targeting
Method	PUT
URL	api.mgid.com/v1/goodhits/campaigns/_ad_campaign_ID_/targetings/operatingsystems
Headers	
Accept: application/json

Authorization: Bearer {token}


Transferred parameters:

Parameter	Value
enabledFlag	on/off OS targeting,  on=1, off=0
targets	_editing_method_,_os_code1_,_os_code2_,_os_code3_
Operating systems:

id	name	version	code
8	Windows OS	Other	windowsos
9	Mac OS	Other	macos
10	Other Desktop OS	 	otherdesctop
11	Android	2.2 and lower	android22mobile
12	Android	2.3	android23mobile
13	Android	3.хх	android3mobile
14	Android	4.0	android40mobile
15	Android	4.1	android41mobile
16	Android	4.2	android42mobile
17	Android	4.3	android43mobile
18	Android	4.4	android44mobile
19	iOS	4.хх and lower	ios4mobile
20	iOS	5.хх	ios5mobile
21	iOS	6.хх	ios6mobile
22	iOS	7.хх	ios7mobile
23	iOS	8.хх	ios8mobile
24	Other Mobile OS	 	othermobile
25	Android	2.2 and lower	android22tablet
26	Android	2.3	android23tablet
27	Android	3.хх	android3tablet
28	Android	4.0	android40tablet
29	Android	4.1	android41tablet
30	Android	4.2	android42tablet
31	Android	4.3	android43tablet
32	Android	4.4	android44tablet
33	iOS	4.хх and lower	ios4tablet
34	iOS	5.хх	ios5tablet
35	iOS	6.хх	ios6tablet
36	iOS	7.хх	ios7tablet
37	iOS	8.хх	ios8tablet
38	Other Tablet OS	 	othertablet
39	Android	5.xx	android50mobile
40	Android	5.xx	android50tablet
41	iOS	9.хх	ios9tablet
42	iOS	9.хх	ios9mobile
43	Android	6.xx	android60mobile
44	Android	6.xx	android60tablet
45	iOS	10.хх	ios10mobile
46	iOS	10.хх	ios70tablet
47	Android	7.xx	android70tablet
48	Android	7.xx	android70mobile
50	iOS	11.xx	ios11mobile
51	iOS	11.xx	ios11tablet
53	Android	8.xx	android80mobile
54	Android	8.xx	android80tablet
55	Android	9.xx	android90mobile
56	Android	9.xx	android90tablet
57	iOS	12.xx	ios12mobile
58	iOS	12.xx	ios12tablet
59	Android	10.хх	android10mobile
60	Android	10.хх	android10tablet
61	iOS	13.хх	ios13mobile
62	iOS	13.хх	ios13tablet
63	Windows OS	10	windowsos10
64	Windows OS	8.1	windowsos81
65	Windows OS	8	windowsos8
66	Windows OS	7	windowsos7
67	Windows OS	Vista	windowsosvista
68	Windows OS	XP	windowsosxp
69	Mac OS	10.12 Sierra	macos1012
70	Mac OS	10.13 High Sierra	macos1013
71	Mac OS	10.14 Mojave	macos1014
72	Mac OS	10.15 Catalina	macos1015
73	Other Smart TV	 	othersmarttv
74	Android	 	androidsmarttv
75	Fire OS (Amazon)	 	fireossmarttv
76	tvOS (Apple TV)	 	tvossmarttv
77	Tizen	 	tizenossmarttv
78	webOS	 	webossmarttv
79	Android	11.xx	android11mobile
80	Android	11.xx	android11tablet
81	iOS	14.хх	ios14mobile
82	iOS	14.хх	ios14tablet
83	Mac OS	11 Big Sur	macos110
84	Roku OS	 	rocuossmarttv
85	Android	12.хх	android12mobile
86	Android	12.хх	android12tablet
87	Mac OS	12 Monterey	macos120
89	iOS	15.xx	ios15mobile
90	Windows OS	11	windowsos11
92	iOS	16.xx	ios16mobile
93	Android	13.хх	android13mobile
94	Android	13.хх	android13tablet
95	iOS	15.xx	ipados15tablet
96	iOS	16.xx	ipados16tablet
97	Mac OS	13 Ventura	macos130
98	iOS	17.xx	ios17mobile
99	iOS	17.xx	ipados17tablet
100	Android	14.xx	android14mobile
101	Android	14.xx	android14tablet
102	Mac OS	14 Sonoma	macos140
103	Android	15.xx	android15mobile
104	Android	15.xx	android15tablet
105	
iOS

18.xx	ios18mobile
106	iOS	18.xx	ipados18tablet
107	Mac OS	15 Sequoia	macos150
108	Android	16.xx	android16mobile
109	Android	16.xx	android16tablet
110	iOS	 26.xx	ios26mobile
111	iOS	 26.xx	ipados26tablet
112	Mac OS	26 Tahoe	macos260
113	Android	
17.xx

android17mobile
114	Android	17.xx	android17tablet
Editing methods :
● include - add OS to the list
● exclude - remove OS from the list
Upon successful saving settings system returns campaign ID:

{
 "id":_campaign_ID_
}
Getting advertising campaign operating system targeting settings
Method	GET
URL	api.mgid.com/v1/goodhits/campaigns/id_campaign/targetings/operatingsystems
Headers	
Accept: application/json

Authorization: Bearer {token}

On success - returns the list of operating systems included:

{
  "targets": [
    "windowsos", 
    "macos",
    "otherdesctop",
    "android22tablet"
  ]
}
Possible errors:

Advertising campaign id doesn't exist or the token of the wrong user used:

{
    "errors": [
        "[ERROR_CAMPAIGN_DOES_NOT_EXIST]"
    ]
}
Empty token:

{
    "errors": "Authentication token is missing"
}
Editing the filter settings on the sites for advertising campaign by UID/source
Method	PATCH
URL	api.mgid.com/v1/goodhits/clients/_client_ID_/campaigns/_ad_campaign_ID_
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters send in the body of the request:

Parameter	Value
widgetsFilterUid	
editing_method, filter_type, uid1,uid2…

you can send sub-source parameters in brackets filter_type, uid1(subid subid sibid),uid2… or through "s" filter_type, UID1sSUBID1...

Available filter types: only / except / off

block-widget-priority

For the edit method include, when it receives a request to add sub_id, it checks whether the source is added to the filter, if added, then the record of the source is ignored. Thus, using this parameter, you can slightly change the query processing logic.

sourceFilters

Only for campaigns with sources optimization enabled, can't be mixed with any other parameters in the request

Can be passed source ID SourceId1, SourceId2, etc. or source name, such as source, source1, etc.

editing_method, filter_type, sourceId1, source2...

Available filter types: allowlist / blocklist / off

Request example:

api.mgid.com/v1/goodhits/clients/{client id}/campaigns/{campaign id}?widgetsFilterUid=include, only, {uid id}s{subid id}&block-widget-priority
Editing methods:

include - include in list
exclude - exclude from the list
On success - returns the identifier of editable ad campaign

{"id":_ad_campaign_ID_}
Example response when users attempt to modify settings via old routes for a campaign using sources optimization:

{"errors":["[ERROR_CAMPAIGN_IS_NOT_TRANSPARENCY_CANT_CHANGE_FILTER]"]}
Error - sources are not passed:

{"errors":["[SOURCES_CANNOT_BE_EMPTY]"]}
Error - nonexistent source IDs or names or invalid sources (e.g., non-integer or incorrect format):

{"errors":["[SOURCES_DO_NOT_EXIST]"]}
Error - invalid filter type (off | blocklist | allowlist | only | except) or missing parameters:

{"errors":["[ERROR_NOT_VALID_FILTER_TYPE]"]}
Error - invalid filter method (include | exclude) or missing parameters:

{"errors":["[ERROR_NOT_VALID_METHOD]"]}
If both valid and invalid sources are passed, valid ones will be saved to the database, and invalid ones will be returned in the error response: 

{"id":_ad_campaign_ID_, "errors":["[SOURCES_DO_NOT_EXIST]"], "data":["1000000","111111","uuuuuu"]}
When a source is blocked at the client level, any attempt to include or exclude it will result in the error:

[SOURCE_CANT_BE_CHANGED_ADDED_TO THE CLIENT_BLOCKLIST]
Error - sites not transferred:

{"errors":["[WIDGETS_IDS_CANNOT_BE_EMPTY]"]}
Error - non-existing sites id transferred:

{"errors":["[WIDGETS_WITH_THESE_IDS_DO_NOT_EXIST]"],"data":["1000000001000"]}
If transferred valid & non-valid IDs ("widgetsFilter": "include, only, ttttts1, 5676301111, 5676672rrr, eeeeee") - valid IDs will be written in the database, for non-valid will be the answer with a list of non-valid IDs:

{"id":_ad_campaign_ID_, "errors":"[WIDGETS_WITH_THESE_IDS_DO_NOT_EXIST]","data":["ttttts1","5676672rrr","eeeeee"]}
When sites are not passed - it's a non-valid situation.

Editing browser language targeting
Method	PUT
URL	api.mgid.com/v1/goodhits/campaigns/_ad_campaign_ID/targetings/browserslanguage
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters send in the parameters of the request:

Parameter	Value
targets*	_ editing_method_ , _ browser_lang_id_,_ browser_lang_id_.....
enabledFlag*	Enable / disable targeting. 0 – target off, 1 — target on
Request example:

api.mgid.com/v1/goodhits/campaigns/{campaign id}/targetings/browserslanguage?enabledFlag=1&targets=include,3,7
Editing methods:

include - include in list
On success - returns the identifier of editable ad campaign:

{"id":_ad_campaign_ID_}
Possible errors:

[ERROR_CAMPAIGN_DOES_NOT_EXIST] - campaign or owner ids not exists or does not match the authorized one
[ERROR_NO_ENOUGH_PARAMETERS] - one of the parameters was not passed, the value of passed languages ids are incorrect, the value is not "include"
[ERROR_INVALID_PARAMETER] - the value is not "include"

Getting browser language targeting settings
 
Method	GET
URL	api.mgid.com/v1/goodhits/campaigns/_ad_campaign_ID/targetings/browserslanguage
Headers	
Accept: application/json

Authorization: Bearer {token}

Request example:

api.mgid.com/v1/goodhits/campaigns/{campaign id}/targetings/browserslanguage
On success - returns the list of languages id:

{
    "targets": [
        34,
        49,
        65
    ]
}
Possible errors:

[ERROR_CAMPAIGN_DOES_NOT_EXIST] - campaign or owner ids not exists or does not match the authorized one

Getting browser targeting settings
 
Method	GET
URL	api.mgid.com/v1/goodhits/campaigns/campaign_id/targetings/browsers
Headers	
Accept: application/json

Authorization: Bearer {token}

Request example:

api.mgid.com/v1/goodhits/campaigns/{campaign id}/targetings/browsers
On success - returns the list of browsers values:

{
  "targets": [
    "chrome",
    "operamobile",
    "firefox"
  ]
}
Possible errors:

[ERROR_CAMPAIGN_DOES_NOT_EXIST] - campaign or owner ids not exists or does not match the authorized one.

Working with client's teasers
Constants and identifiers in use
Currency code to display the price of the product:

id	combname	name_utf
1	rub	руб
4	uah	грн
5	usd	$
6	eur	€
9	byn	руб
12	inr	र
23	ils	₪
35	gel	₾
38	kzt	₸
43	aed	د.إ
46	inr	₨

Teaser status:

Status	Description
onModeration	Teaser on moderation
rejected	Teaser is rejected
active	Teaser is active
new	New teaser, don't have CTR yet
goodPerformance	Teaser is in shows
badPerformance	Teaser have no shows in one or more regions because have low rating. It is necessary to set a higher price per click or replace the teaser on the other, which could provide a higher CTR
blocked	Blocked teaser
campaignBlocked	Blocked campaign
 

Getting a list of client teasers
Method	GET
URL	api.mgid.com/v1/goodhits/clients/_client_ID_/teasers[/_teaser_ID_]
Headers	
Accept: application/json

Authorization: Bearer {token}


If _teaser_ID_ is not passed, then method returns a list of client teasers. If _teaser_ID_ is passed, then method returns information about current teaser.

Transferred parameters (required parameters are marked with asterisk *):

Parameters	Value
fields
(optional, use if passed _teaser_ID_)	Array of teaser properties, information
about which  necessary to obtain(for example:
fields=['title','url','statistics']).  If the parameter is not passed, then returns  all  Properties.
status	Takes values from the table "Teaser statuses"; You can specify several statuses simultaneously (for example: status = ['active', 'onModeration']) to get all teasers with these statuses.
blockedBy	
This parameter is an additional option that works together with the status filter. It allows checking and filtering teasers by the entity that applied the action leading to the current status.

Supported statuses: onModeration, rejected, active, new, blocked.

Possible values:

client: blocked by the client (dashboard / API action);
account_manager: blocked by an MGID Account Manager user;
system:  blocked by the system (e.g., cron, schedule, automation);
moderator: blocked by a moderator or scheduled moderation action.
creationDate	
Allows filtering creatives by their creation date range. It is designed to help retrieve only those creatives that were created within a specific time period.

Format:

The parameter accepts two optional sub-parameters:

creationDate[dateFrom] — start date (>=)
creationDate[dateTo] — end date (<)
Date format: Y-m-d (e.g., 2025-08-01)

campaign	Getting a list of clients' teasers by campaign ID
limit	Limiting the number of teasers displayed on the page. If doesn't set - shows all teasers. Possible error when using the option limit: ["[ERROR_MAX_LIMIT_PER_PAGE_{max_allowed_limit}]"]
start	Sets the position of the element. Default - 0. For example: at the first request start = 0 limit = 700, the next request will be: start = 700 limit = 700. 
ctrGuard*	
Returns appropriate teasers created with CTR Guard. Value: 1.

*when this filter is applied, all other filters - except for "campaign" - are disregarded.Request example:

Request example for the blockedBy parameter to show teasers blocked by the client:

api.mgid.com/v1/goodhits/clients/{clientId}/teasers/status=["blocked"]&blockedBy=client
Request example for the blockedBy parameter to show active and blocked teasers blocked by a moderator:

api.mgid.com/v1/goodhits/clients/{clientId}/teasers/status=["active", "blocked"]&blockedBy=moderator
Request example for the creationDate parameter:

api.mgid.com/v1/goodhits/clients/{clientId}/teasers/?creationDate[dateFrom]=2025-08-27&creationDate[dateTo]=2025-09-05
Answer returned:

{  
"_teaser_ID_":
        {
         "id":"_teaser_ID_",
         "title":"_teaser_titel_",
         "advertText":"_advertising text teaser_",
         "url":"_ advertising_link_",
         "imageLink":"_link_to_teaser_image_",
         "cropLeft":"_cropping_the_image_on_the_left _",
         "cropTop":"_cropping_the_image_on_top _",
         "cropWidth":"_width_of_cropping_part_",
         "priceOfClickByLocations":                
                [{"locationId":"_geo_group_id_",
                "locationName":"_geo_group_name_",
                "priceOfClick":"_price_of_click_by_geo_group_"},...]

         "goodPrice":_product_price_,
         "goodOldPrice":_ old_product_price _,
         "currency":_ currency_ID_to_display_the_price_of_product_,
         "category":
                 {
                "id":"_category_ID_", "name":"_category_name_"
                },
         "campaignId":_campaign_ID_,
         "status":"_teaser_status_",
         "reason_if_drop_karantin": _reason_rejection_ (displayed if teaser a rejected),
         "statistics":
                 {
                 "clicks":_total_clicks_,
                 "clicks_today": _today_clicks_,
                 "clicks_yesterday": _yesterday_clicks_,  
                 "hits":_total_shows_,
                 "hits_today": _today_shows_,
                 "hits_yesterday": _yesterday_shows_,  
                 "spent":_spent_all_,
                 "spent_today":_spent_today_,
                 "spent_yesterday":_spent_yesterday_,
                 "ctr":"_teaser_CTR_",

         "ctr_by_locations":          
                [{"locationId":"_geo_group_id_",
                "locationName":"_geo_group_name_",
                "ctr":"_ctr_by_geo_group_"},...]

           },

         "conversion":
                {
                "interest_all": _number_of_achievements_interest_stage_ for_all_time_,
                "decision_all":  _number_of_achievements_decision_stage_ for_all_time_,
                "buying_all":  _number_of_achievements_buying_stage_ for_all_time_,
                "interest_yesterday": _number_of_achievements_interest_stage_ for_yesterday_,
                "decision_yesterday": _number_of_achievements_decision_stage_ for_yesterday_,
                "buying_yesterday": _number_of_achievements_buying_stage_ for_yesterday_

         }
        },
"_teaser_ID_2_":
{ . . . . . . },
. . . . . . . . . }
If an invalid date is provided, return the error:

[ERROR_INVALID_CUSTOM_DATES]
 

 

 

Teaser detailed daily statistics
Method	GET
URL	api.mgid.com/v1/goodhits/clients/{authId}/teaser-stat/{teaserId}?dateInterval={interval}
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters (required parameters are marked with asterisk *):

Parameters	Value
uid	returns teaser statistics for specified widget uid
dateInterval	
Period for which you need to get statistics. If interval is not specified, returns statistics for 30 days. Valid values are:

interval - need to 2 specify additional parameters: startDate and endDate in format yyyy-mm-dd
all - last 90 days
thisWeek - current week
lastWeek - last week
thisMonth - current month
lastMonth - last month
lastSeven - last 7 days
today - today
yesterday - yesterday
last30Days - last 30 days
Answer returned:

{
  "dateInterval": "2021-01-11 - 2021-01-12",
  "timezone": "Asia\/Ho_Chi_Minh",
  "currency": "usd",
  "status": "active",
  "teaser-stat": {
   "2021-01-11": {
    "date": "2021-01-11",
    "clicks": 47,
    "shows": 33289,
    "ctr": 0.141188,
    "spent": 0.157888,
    "cpc": 0.335932,
    "interest": 0,
    "decision": 0,
    "buy": 11,
    "interestCost": 0,
    "decisionCost": 0,
    "buyCost": 0.014353
  },
  "2021-01-12": {
   "date": "2021-01-12",
   "clicks": 263,
   "shows": 123850,
   "ctr": 0.212354,
   "spent": 0.389839,
   "cpc": 0.148228,
   "interest": 0,
   "decision": 0,
   "buy": 14,
   "interestCost": 0,
   "decisionCost": 0,
   "buyCost": 0.027846
  }
 }
}
If there are some errors:

{"errors":["[_error_]"]}
[THERE_NO_DATA_IN_CHOSEN_PERIOD] - if there is no data in chosen period

[INVALID_VALUE_FOR_INTERVAL] - invalid value for interval

[TEASER_DOES_NOT_EXIST] - teaser not exists

 

Creating a new teaser for ad campaign
Method	POST
URL	api.mgid.com/v1/goodhits/clients/_client_ID_/teasers
Headers	
Accept: application/json

Authorization: Bearer {token}


Transfered parameters (required parameters are marked with asterisk * must be transferred in POST method body)

Parameters	Value
url*	URL advertising links. It's recommended to use %26 instead of & during parameters transmission
campaignId*	Campaign ID to which is teaser added
title*	
Teaser title

for content/product/search feed campaign type - up to 90 characters
for push campaign type - up to 30 characters
supported macros: {City}, {Country}, {Region} - the macro must be capitalized, use curly braces, and be specified only in English. It is forbidden to use macros for a push campaign type
advertText	
Advertising text. If this parameter is passed in the request, the validation will be as follows:

for content/product/search feed campaign type - up to 90 characters (optional)
for push campaign type - up to 40 characters (required)
The parameter is required if Geo-targeting has been set to Germany

imageLink*	
Link to teaser image.

Minimum size 492x328 pixels.
Recommended size 600x382 pixels and larger.
Available formats: .jpg/.jpeg/.png and .gif/.mp4/.mov.
categoryId*	
Teaser category ID. This parameter must be passed for Push campaign type only. For Product, Content, and SearchFeed campaign types category will be set automatically

priceOfClick*	Price per click, cents, with tenths. As a separator
between the whole number and the fraction can use a comma or period.
whetherShowGoodPrice*	
Flag display the price of goods (1/0)

If whetherShowGoodPrice = 1 parameters currency, goodPrice, goodOldPrice are required. If whetherShowGoodPrice = 0 then the following parameters will be ignored.

currency	Currency ID to display the price of the product
goodPrice	Price of the goods in a specified currency
goodOldPrice	Old price of the goods.
callToAction	
Optional field. One of the call-to-action options available for a teaser, selected from the predefined dictionary (see: “Getting an available CTA for an advertiser's campaign”).

 

Categories list:

id	name	campaign types
100	Automotive	product, video, offer, push, search_feed
101	Books and Literature	product, video, offer, push, search_feed
103	Events	product, video, offer, push, search_feed
105	Casinos and Gambling	product, video, offer, push, search_feed
107	Marriage and Civil Unions	product, video, offer, push, search_feed
108	Dating	product, video, offer, push, search_feed
109	Pick up	product, video, offer, push, search_feed
111	World Cuisines	product, video, offer, push, search_feed
112	Alcoholic Beverages	product, video, offer, push, search_feed
114	Nutrition	product, video, offer, push, search_feed
115	Weight Loss	product, video, offer, push, search_feed
116	Women's Health	product, video, offer, push, search_feed
117	Children's Health	product, video, offer, push, search_feed
118	Fitness and Exercise	product, video, offer, push, search_feed
120	Alternative Medicine	product, video, offer, push, search_feed
121	Smoking Cessation	product, video, offer, push, search_feed
122	Muscle Building	product, video, offer, push, search_feed
123	Brain Booster	product, video, offer, push, search_feed
126	Home Security	product, video, offer, push, search_feed
127	Home Improvement	product, video, offer, push, search_feed
128	Gardening	product, video, offer, push, search_feed
131	Sleep Disorders	product, video, offer, push, search_feed
132	Diabetes	product, video, offer, push, search_feed
133	Varicosis	product, video, offer, push, search_feed
134	Bone and Joint Conditions	product, video, offer, push, search_feed
135	Eye and Vision Conditions	product, video, offer, push, search_feed
136	Psoriasis	product, video, offer, push, search_feed
137	Papilloma	product, video, offer, push, search_feed
138	Skin and Dermatology	product, video, offer, push, search_feed
139	Medical Services	product, video, offer, push, search_feed
141	Foot Health	product, video, offer, push, search_feed
143	Hemorrhoid	product, video, offer, push, search_feed
144	Prostatitis	product, video, offer, push, search_feed
145	Sexual Health	product, video, offer, push, search_feed
148	Stocks and Bonds	product, video, offer, push, search_feed
149	Options	product, video, offer, push, search_feed
150	Insurance	product, video, offer, push, search_feed
151	Personal Debt	product, video, offer, push, search_feed
152	Financial Assistance	product, video, offer, push, search_feed
153	Retirement Planning	product, video, offer, push, search_feed
154	Real Estate	product, video, offer, push, search_feed
156	For Kids	product, video, offer, push, search_feed
157	Gifts and Souvenirs	product, video, offer, push, search_feed
159	Couponing	product, video, offer, push, search_feed
161	Sporting Goods	product, video, offer, push, search_feed
162	Fishing Sports	product, video, offer, push, search_feed
165	Makeup and Accessories	product, video, offer, push, search_feed
166	Natural and Organic Beauty	product, video, offer, push, search_feed
167	Skin Care	product, video, offer, push, search_feed
168	Hair Care	product, video, offer, push, search_feed
169	Perfume and Fragrance	product, video, offer, push, search_feed
170	Other Beauty Products	product, video, offer, push, search_feed
172	Oral Care	product, video, offer, push, search_feed
173	Shaving	product, video, offer, push, search_feed
176	Women's Intimates and Sleepwear	product, video, offer, push, search_feed
177	Women's Outfits	product, video, offer, push, search_feed
179	Women's Jewelry and Watches	product, video, offer, push, search_feed
180	Other Women's Accessories	product, video, offer, push, search_feed
181	Women's Shoes and Footwear	product, video, offer, push, search_feed
184	Men's Underwear and Sleepwear	product, video, offer, push, search_feed
185	Men's Outfits	product, video, offer, push, search_feed
187	Men's Jewelry and Watches	product, video, offer, push, search_feed
188	Other Men's Accesories	product, video, offer, push, search_feed
189	Men's Shoes and Footwear	product, video, offer, push, search_feed
190	Children's Clothing	product, video, offer, push, search_feed
193	Laptops	product, video, offer, push, search_feed
194	Desktops	product, video, offer, push, search_feed
195	Computer Peripherals	product, video, offer, push, search_feed
196	Computer Software and Applications	product, video, offer, push, search_feed
198	Smartphones	product, video, offer, push, search_feed
199	Tablets and E-readers	product, video, offer, push, search_feed
200	Cameras and Camcorders	product, video, offer, push, search_feed
201	Wearable Technology	product, video, offer, push, search_feed
202	Energysavers	product, video, offer, push, search_feed
203	Self Defense	product, video, offer, push, search_feed
204	Solar Panels	product, video, offer, push, search_feed
205	Other Electronics	product, video, offer, push, search_feed
206	Travel	product, video, offer, push, search_feed
207	Video Gaming	product, video, offer, push, search_feed
208	Automotive	content
209	Business and Finance	content, push
211	Education	content, push
212	Events and Attractions	content
213	Family and Relationships	content
219	Cooking	content
220	Alcoholic Beverages	content
221	Healthy Living	content
225	Hobbies and Interests	content, push
229	Home and Garden	content
230	Movies	content, push
232	News and Politics	content, push
237	News Ukraine	content, push
238	Pets	content
239	Pop Culture	content, push
241	Science	content, push
242	Sports	content
243	Style and Fashion	content
247	Technology and Computing	content
249	Travel	content
251	Pets	product, offer, push, search_feed
252	Ear, Nose and Throat Conditions	product, push, search_feed
254	Currencies	product, offer, push, search_feed
258	Lottery	product, video, offer, push, search_feed
260	Content Media Format	product, push, search_feed
261	Other services	product, push, search_feed
262	Charity Funds	product, push, search_feed
263	Business Services	product, push, search_feed
264	Education	product, push, search_feed
265	Legal Services Industry	product, push, search_feed
266	Language Learning	product, push, search_feed
267	Delivery	product, push, search_feed
268	Mobile Services	product, push, search_feed
270	Blood Disorders	product, push, search_feed
271	Digestive Disorders	product, push, search_feed
272	Endocrine and Metabolic Diseases	product, push, search_feed
278	Business I.T.	product, push, search_feed
280	Infectious Diseases	product, push, search_feed
281	Cancer	product, push, search_feed
282	Contests and Competitions	product, video, offer, push, search_feed
Answer returned:
Upon successful creation of the teaser response is returned:

{
 "id":_new_teaser_ID_,
}
Returns an error name if the attempt to create a teaser was a failure:

{"errors":["[_ error_name_ _]"] }
If a teaser has macros in the teaser title or description for Push campaign:

{"errors":["[VALIDATION_MACRO_WAS_FOUND_TITLE_PUSH]"] }
If a teaser has an irrelevant link format, the system returns an error:

{"errors":["[LS_IMAGE_WRONG_EXTANTION]"]}
If the teaser has a size less than the minimum, return an error (where X or Y - an irrelevant size for width or height)
"errors": [
 "Minimum expected width for image '' should be '492' but 'X' detected,Minimum expected height for image
 '' should be '328' but 'Y' detected"]
The list of possible errors returned in the creation and editing teaser of the campaign:

_ERROR_NAME_	specification
ERROR_PARAMETER_WHETHERSHO WGOODPRICE_CAN_NOT_BE_EMPTY	Not passed a required parameter whetherShowGoodPrice
ERROR_PARAMETER_PRICEOFCLICK_ CAN_NOT_BE_EMPTY	Not passed a required parameter priceOfClick
ERROR_PARAMETER_CATEGORY_CA N_NOT_BE_EMPTY	Not passed a required parameter category
ERROR_ADVERT_TEXT_TOO_LONG	Advertising text (parameter advertText) exceeds the maximum allowed length (no more than 75 characters)
ERROR_PARAMETER_TITLE_CAN_NO T_BE_EMPTY	Not Transfered teaser title (required parameter title)
ERROR_TITLE_TOO_LONG	Title teaser (parameter title) exceeds the maximum allowed length (no more than 65 characters)
ERROR_PARAMETER_IMAGELINK_CA N_NOT_BE_EMPTY	Not assigned image link for the teaser (required parameter imageLink)
ERROR_PARAMETER_CAMPAIGNID_CA N NOT_BE_EMPTY	Not transmitted campaign ID that creates teaser (required parameter campaignId)
ERROR_PARAMETER_URL_CAN_NOT_BE _EMPTY	Not assigned to an advertising link to the teaser (required parameter url)
[ERROR_PARAMETER_CATEGORY_INCORRECT_FOR_THIS_CAMPAIGN_TYPE]	Improperly selected category for this type of campaign
[ERROR_PARAMETER_POST_SEND]	You must use method POST in this request
[ERROR_MGCLID_MGCLIDA_SYSTEM_PARAMETERS_CANNOT_USE_THEM]	Cannot use adclid or adclida
[ONE_OR_MORE_REGIONS_HAVE_PRICE_HIGHER_THAN_ACCEPTABLE_PRICE]	No valid CPC
 

Editing ad campaign teaser settings
Method	PUT
URL	api.mgid.com/v1/goodhits/clients/_client_ID_/teasers/_teaser_ID_
Headers	
Accept: application/json

Authorization: Bearer {token}


Transfered parameters (required parameters are marked with asterisk *):

Parameters	Value
url*	URL advertising links
campaignId*	Campaign ID to which is teaser added
title*	
Teaser title

for content/product campaign type - up to 65 characters
for push campaign type - up to 30 characters
advertText*	
Advertising text. If this parameter is passed in the request, the validation will be as follows:

for content/product campaign type - up to 75 characters (optional)
for push campaign type - up to 40 characters (required)
If the parameter has not been passed, it will not be changed.

imageLink*	
Link to teaser image.

Minimum size 492x328 pixels.
Recommended size 600x382 pixels and larger.
Available formats: .jpg/.jpeg/.png and .gif/.mp4/.mov.
category*	
Teaser category ID

whetherShowGoodPrice*	
Flag display the price of goods (1/0)

If whetherShowGoodPrice = 1 parameters currency, goodPrice, goodOldPrice are required. If whetherShowGoodPrice = 0 then the following parameters will be ignored.

    currency	Currency ID to display the price of the product
    goodPrice	Price of the goods in a specified currency
    goodOldPrice	Old price of the goods.
If any of the required parameters weren't passed, the system returns an error.

For example, not transmitted campaignId:

 {"errors":["[ERROR_PARAMETER_CAMPAIGNID_CAN_NOT_BE_EMPTY]"]}
If teaser on moderation, the system returns an error:

{"errors":["[ERROR_EDITING_TEASER_ON_MODERATION_NOT_PERMITTED]"]}
Cannot use adclid or adclida
{"errors":["[ERROR_MGCLID_MGCLIDA_SYSTEM_PARAMETERS_CANNOT_USE_THEM]"]}
If a teaser has an irrelevant link format, the system returns an error:

{"errors":["[LS_IMAGE_WRONG_EXTANTION]"]}
If the teaser has a size less than the minimum, return an error (where X or Y - an irrelevant size for width or height)
"errors": [
 "Minimum expected width for image '' should be '492' but 'X' detected,Minimum expected height for image
 '' should be '328' but 'Y' detected"]
 

 

 

Changing advertising campaign teaser's CPC
Method	PATCH
URL	api.mgid.com/v1/goodhits/clients/_client_ID_/teasers/_teaser_ID_
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred parameters send in the body of the request:

Parameter	Value
priceOfClick	Installed CPC in tenth of cents for all geo groups. Can be used a period or comma as a delimiter.
Answer returned.
If all done correctly, system return an answer:

{ 
 "id":_teaser_ID_,
}
Some errors:
● if the parameter CPCs not specified or incorrect:

{"errors":["[EDIT_PRICE_REQUIRED_PRICES]"]}
● if the price is not indicated or specified is not a valid value:

{"errors":["[VALIDATION_NOT_FLOAT]","[VALIDATION_NOT_FLOAT]"]}
● if the price is less than minimum:

{"errors":["The price is not valid"]}
● if the price is higher than  maximum:

{"errors":["[LS_CAB_'51'_MORE_THAN_'50']","[LS_CAB_'51'_MORE_THAN_'50']"]}
if the CPC is not valid
{"errors":["[ONE_OR_MORE_REGIONS_HAVE_PRICE_HIGHER_THAN_ACCEPTABLE_PRICE]"]}
 

Block / unblock a teaser for advertising campaign
Method	PATCH
URL	api.mgid.com/v1/goodhits/clients/_client_ID_/teasers/_teaser_ID_
Headers	
Accept: application/json

Authorization: Bearer {token}


Transferred parameters send in the body of the request:

Parameters	Value
whetherToBlockByClient	1 — block
0 — unblock
Answer returned.
If the operation is successful, it returns teaser ID:

{
 "id":"_teaser_ID_"
}
 

Removing teaser (move to bin)  
Method	DELETE
URL	api.mgid.com/v1/goodhits/clients/_client_ID_/teasers/_teaser_ID_
Headers	
Accept: application/json

Authorization: Bearer {token}

Answer returned:
If the operation is successful, it returns teaser ID which was moved to bin:

{
 "id":"_teaser_ID_"
}
If a teaser with the specified ID does not exist in the system or have already been
moved to the bin, then the message will be returned:

[ERROR_RESOURCE_NOT_FOUND]

Granular statistics reports
This endpoint allows users to retrieve campaign performance data with fine-grained filtering and breakdowns.

Method	GET
URL	/v1/goodhits/clients/{client_id}/statistics-reports
Headers	
Accept: application/json

Authorization: Bearer {token}

Transferred Parameters (required marked with *)

Parameter

Type

Description

filters[dateRange][dateFrom] *

string

Start date in ISO format 

YYYY-MM-DDTHH:mm:ss.sssZ

filters[dateRange][dateTo] *

string

End date in ISO format 

YYYY-MM-DDTHH:mm:ss.sssZ

(max range = 90 days)

metrics[] *

array

At least 1 metric must be passed. See the list below.

dimensions[] *

array

At least 1 dimension (max 3). See the list below.

limit

integer

Max number of records to return (default = 20, max = 1000)

offset

integer

Offset for pagination

orders[<metric> or <dimensions>]

string

Sorting order by metric field: asc or desc

filters[countries][]

array

Country codes. See country list

filters[regions][]

array

Region codes. See region list

filters[os][]

array

OS codes. See OS list

filters[browsers][]

array

Browser codes. See browser list

filters[deviceTypes][]

array

Device types: desktop, mobile, tablet, smarttv

filters[campaigns][]

array

Campaign IDs

filters[teasers][]

array

Teaser IDs

Dimensions (max 3)

month
week
day
hour
campaignId
campaignName
campaignType
teaserId
country
region
os
browser
deviceType
widgetId
source
Metrics

adRequests

clicks

impressions

viewability

spent

cpc

cpcWithoutDataFee

ctr

epc

vCtr

vCpm

revenue

profit

roas

conversionsInterest

conversionsDecision

conversionsBuy

conversionsRateInterest

conversionsRateDecision

conversionsRateBuy

conversionsCostInterest

conversionsCostDecision

conversionsCostBuy

Validation Rules

Max date range = 90 days

Max dimensions = 3

Must pass at least 1 metric and 1 dimension

Sorting only allowed by metrics or dimensions

Sample Request

GET /v1/goodhits/clients/111/statistics-reports?limit=5&offset=0&orders[clicks]=desc&filters[dateRange][dateFrom]=2025-03-01T00:00:00.000Z&filters[dateRange][dateTo]=2025-03-20T23:59:59.999Z&filters[countries][]=54&metrics[]=cpc&metrics[]=clicks&dimensions[]=hour&dimensions[]=campaignId&dimensions[]=campaignName
Sample Response

{

  "data": [

    {

      "hour": 21,

      "campaignId": 0,

      "campaignName": "name",

      "clicks": 1120,

      "spent": {

        "amount": "840",

        "currency": "USD"

      },

      "cpc": {

        "amount": "0.75",

        "currency": "USD"

      }

    },

    {

      "hour": 20,

      "campaignId": 1,

      "campaignName": "name1",

      "clicks": 1018,

      "spent": {

        "amount": "763.5",

        "currency": "USD"

      },

      "cpc": {

        "amount": "0.75",

        "currency": "USD"

      }

    },

    {

      "hour": 22,

      "campaignId": 2,

      "campaignName": "name2",

      "clicks": 989,

      "spent": {

        "amount": "741.75",

        "currency": "USD"

      },

      "cpc": {

        "amount": "0.75",

        "currency": "USD"

      }

    },

    {

      "hour": 19,

      "campaignId": 3,

      "campaignName": "name3",

      "clicks": 974,

      "spent": {

        "amount": "730.5",

        "currency": "USD"

      },

      "cpc": {

        "amount": "0.75",

        "currency": "USD"

      }

    },

    {

      "hour": 15,

      "campaignId": 4,

      "campaignName": "name4",

      "clicks": 831,

      "spent": {

        "amount": "623.25",

        "currency": "USD"

      },

      "cpc": {

        "amount": "0.75",

        "currency": "USD"

      }

    }

  ],

  "totals": {

    "hour": 0,

    "campaignId": 0,

    "campaignName": "",

    "clicks": 15494,

    "spent": {

      "amount": "11611.5228",

      "currency": "USD"

    },

    "cpc": {

      "amount": "0.749420601",

      "currency": "USD"

    }

  },

  "count": 43,

  "limit": 5,

  "offset": 0

}

Example Error Responses

Too many dimensions:
{

  "errors": {

    "dimensions": ["This collection should contain 3 elements or less."]

  }

}
Date range exceeds 90 days:
{

  "errors": ["Date range exceeds 90 day limit"]

}
Metric not valid:
{

  "errors": {

    "metrics[0]": ["The value you selected is not a valid choice."]

  }

}




REST API MGID for Publishers

The main provisions of REST API
REST API allows you to integrate external applications with Mgid online  
advertising system.

API provides the ability to retrieve, add, and modify the data. Practically each  object in Mgid (whether it's a client, an advertising company, a teaser, etc.) can  be controlled by API. Mgid REST API Request is an HTTP request, which, with  the help of the ways in URL the object to perform the action is specified, and  with the help of parameters the necessary data is passed. Mgid API is a "RESTful  Web API". The API uses the following REST commands:

GET

PUT

PATCH

POST

DELETE

The query parameters are case sensitive.

These commands correspond to certain actions within the Mgid system. Get an item or a collection of items (for example, a list of advertising campaigns):    

Command	Action	Description
POST	Create	Creates a new element (eg, a teaser)
GET	Get (read)   	Retrieve an element or a collection of elements
PUT	Update	Recreate an existing element or a collection of elements
PATCH	Change	Change certain properties of an element
DELETE	Delete	Delete an item or collection of items (eg, move a teaser to recycle bin)
Important! POST and PUT are not interchangeable. Each of the commands fulfills its specific function.

In general, the query looks like this:
https://api.mgid.com/v1/module/controller/action?parameter_1=value_of_parameter_1&parameter_2=value_of_parameter_2&parameter_3=value_of_parameter_3

 

Identification
For identification the Mgid REST API uses a unique token consisting of 32 characters which is passed in client’s request Authorization header. To obtain a valid token client should use a special API function.

Every request sent to the Mgid REST API must contain the API token
 

MGID REST API Answer
In response to a request to the REST API server always returns the HTTP response with a status code , depending on the result of the query.

Answer code	Description
200 OK	The query has been successfully
processed
400 Bad Request	Syntax error
404 Not Found	Item or page not found
Format of the returned data
The returned data can be formatted as JSON, or XML.  The default format is JSON. The request header is used to specify the format in which the data is  
returned. The client sends an Accept header, which indicates desired response format:  
Accept: application / xml  
or  
Accept: application / json

A description of the response format is sent in the response header Content Type. The data returned is the answer is a JSON string, which generally looks as follows:  

{
    "element_1":"value_of_element_1",    
    "element_2":"value_of_element_2", 
    "element_3":{
         "property_1_of_element_3":"value_of_property_1_of_element_3",       
         "property_2_of_element_3":[
               "value_1_of_property_2_of_element_3",
               "value_2_of_property_2_of_element_3"
         ]       
     }    

  . . . .  
}
If an error has occurred during the execution of the query   the description corresponding to the error is returned, such as:

{ "errors": [ "[_error_description_]" ] }
 

Working with widgets
Custom reports
Method	GET
URL	api.mgid.com/v1/publishers/{authId}/widget-custom-report
Header	
Accept: application/json

Authorization: Bearer {token}

Transfered parameters (required parameters are marked with asterisk *):

Parameter	Value
dateInterval*	
Interval of time you need to get a statistics. Valid values:

interval - if selected, must be specified startDate/endDate in format yyyy-mm-dd
all
thisWeek - starting from Monday
lastWeek - starting from Monday
thisMonth
lastMonth
lastSeven
today
yesterday
last30Days
In addition, you can transfer the hour intervals:

startHour - start hour 0-23
endHour - end hour 0-23
siteId	
Client's site ID

If presented stats will be provided for particular website.
If not presented - stats will be provided for the whole account (considering the dimensions)
dimensions*	
list of fields to group. It can take multiple values separated by a comma. Valid values are:

date
widgetId
deviceType
subId
countryIso
widgetName
domain
trafficType
trafficSource
metrics*	
list of fields for extracting indicators. It can take multiple values separated by a comma. Valid values are:

shows [deprecated]
realShows [deprecated]
pageViews [deprecated]
adRequests
impressions
visibilityRate
clicks
wages
cpm
vCpm [deprecated]
eCpm
cpc
ctr
videoImpressions
page	page number with statistics
perPage	records number per page. Default 1000, maximum 100 000, minimum 1
widgetId	composite widget ID 
deviceType	device type (desktop, tablet, mobile)
countryIso	country code (alpha2)
sortBy	sort by field (can take one of the transmitted values dimensions or metrics), if not passed, sorts by the first parameter from dimensions
sortMethod	direction of sorting (asc, desc), if not sent then applied ASC direction
timeZone	Timeshift of statistics. Available list of timeZones here ( TZ ). If the parameter not passed timeZone will be set to America/Los_Angeles
 
Website Custom Report
Retrieve statistics aggregated at the website level. Use this endpoint when you need website-scoped metrics — including pageviews — instead of per-widget breakdowns.

Method

GET

URL

https://api.mgid.com/v2/pub/account/{clientId}/website-custom-report

Header

Accept-Language: en

Authorization: Bearer {token}

Content-Type: application/json

Required Parameters

Parameter

Type

Description

dateInterval

string

Time period for the report. See Date interval values below.

dimensions

string

Comma-separated list of fields to group results by. Accepts multiple values. See Dimensions below.

metrics

string

Comma-separated list of metric fields to return. Accepts multiple values. See Metrics below.

Optional Parameters

Parameter

Type

Description

website

string

Filter results to one or more websites. Accepts comma-separated domain names (e.g., example.com,other.com). Omit returning account-wide data.

startHour

integer

Start the hour filter (0–23). Use with endHour to narrow results to a time window within each day.

endHour

integer

End hour filter (0–23).

limit

integer

Records per page. Default: 1000. Min: 1. Max: 100000.

offset

integer

Pagination offset (number of records to skip). Default: 0.

orders\[{field}\]

string

Sort results by any dimension or metric. Replace {field} with the field name. Value: asc or desc. Example: orders\[revenue\]=desc.

timeZone

string

TZ database timezone identifier (e.g., America/New_York). Default: America/Los_Angeles.

Date Interval Values

Available presets:

today

yesterday

thisWeek

lastWeek

thisMonth

lastMonth

lastSeven

last30Days

last90Days

For a custom range, use interval with startDate and endDate in yyyy-mm-dd format.

Dimensions

Value

Description

date

Groups results by day

website

Groups results by website domain

countryIso

Groups results by two-letter ISO country code

deviceType

Groups results by device type (desktop, tablet, mobile)

OS

Groups results by operating system

trafficType

Groups results by traffic type

trafficSource

Groups results by traffic source

Metrics

Value

Description

pageViews

Total number of page views

viewWithVisibility

Impressions with viewability measured

visibilityRate

Percentage of visible impressions

revenue

Total publisher revenue

adCTR

Ad click-through rate

advCTR

Advertiser click-through rate

adCPC

Ad cost per click

adCPM

Ad cost per thousand impressions

advCPM

Advertiser CPM

orgClicks

Organic clicks

orgCTR

Organic click-through rate

orgvCTR

Organic viewable click-through rate

Example Request

curl -X GET \

"https://api.mgid.com/v2/pub/account/{clientId}/website-custom-report?dateInterval=last30Days&dimensions=date,website&metrics=pageViews,revenue&website=example.com&orders[revenue]=desc&limit=100" \

-H "Accept-Language: en" \

-H "Authorization: Bearer {token}" \

-H "Content-Type: application/json"
Example Response

[

{

"date": "2025-04-01",

"website": "example.com",

"pageViews": 124500,

"revenue": 42.15

},

{

"date": "2025-04-02",

"website": "example.com",

"pageViews": 131200,

"revenue": 47.80

}

]
Error Response

{

"errors": ["[error_description]"]

}
Common error codes:

422 Unprocessable Entity — Missing or invalid required parameters. The response body includes a descriptive error message.
401 Unauthorized — Missing or invalid authorization token.


REST API MGID for Advertising Agencies
Getting advertising agency clients list  with financial stats
Method	GET
URL	api.mgid.com/v1/agencies/{accountId}/clients
Headers	
Accept: application/json

Authorization: Bearer {token}

Transfered parameters:

Parameter	Value
accountId	Identifier of user (advertising agency) account
Returned answer:

{
   clients:{
       "id":_identifier_of_client's_account_,
         "email":_client's_email_,
      "wallet":{
         "balance":_state_of_MG_wallet_,
         "credit":_overdraft_amount_,
         "income":_total_replenish_sum_
      }
   }
}
All sums tranfered in advertising agency currency.

Possible errors:

If transferred current token is invalid, returned error is "invalid token".

 

Getting one client financial stats
Method	GET
URL	api.mgid.com/v1/agencies/{accountId}/clients/{client_id}
Headers	
Accept: application/json

Authorization: Bearer {token}

Transfered parameters:

Parameter	Value
accountId	Identifier of user (advertising agency) account
client_id	Advertising agency client id
Returned answer:

{
    "id":_identifier_of_client's_account_,
   "wallet":{
      "balance":_state_of_MG_wallet_,
      "credit":_overdraft_amount_,
      "income":_total_replenish_sum_
   }
}
All sums tranfered in advertising agency currency

Possible errors:

If transferred current token is invalid, returned error is "invalid token";

If client id is incorrect returned answer is "Invalid client id".

 

Getting financial stats of advertising agency
Method	GET
URL	api.mgid.com/v1/agencies/{accountId}
Headers	
Accept: application/json

Authorization: Bearer {token}

Transfered parameters:

Parameter	Value
accountId	Identifier of user (advertising agency) account
Returned answer:

{
    "id":_identifier_of_user(advertising_agency)_account_,
   "balance":{
      "personal_account":_balance_on_main_wallet_,
      "bonus_account":_balance_on_bonus_wallet_,
      "clients_balance":_sum_of_cuurent_clients_balances_
   }
}
All sums tranfered in advertising agency currency.

Possible errors:

If transferred current token is invalid, returned error is "invalid token".

 

Getting data of advertising agency clients expences for a period
Method	GET
URL	api.mgid.com/v1/agencies/{accountId}/clients-spent-reports
Headers	
Accept: application/json

Authorization: Bearer {token}

Transfered parameters:

Parameter	Value
accountId	Identifier of user (advertising agency) account
dateStart	Period start date in format  YYYY-MM-DD
dateEnd	Period end date in format YYYY-MM-DD
clientsIds	Clients ids separated by commas, not nesessary parameter
Returned answer:

{
   dateStart:Period start date in format YYYY-MM-DD,
   dateEnd:Period end date in format  YYYY-MM-DD,
   clients-spent-reports:[
      {
         "id":_identifier_of_client's_account_,
         "spent":_sum_of_expences_by_directions_(goodhits +news + banners)
      },

   ]
}
All sums transfered in advertising agency currency.

If parameter clientsIds is empty, return expenses for all advertising agency clients.

Possible errors:

If the transferred current token is invalid, returned error is "invalid token";

If client id is incorrect returned answer is "Invalid client id";

Possible format errors of parameters: dates should be in the format of YYYY-MM-DD, clientsIds should be separated by commas.

 

Clients balance replenishments from advertising agency wallet
Method	POST
URL	api.mgid.com/v1/agencies/{accountId}/clients/{client_id}/money-transfers?account_type={account_type}&transfer_amount={transfer_amount}
Headers	
Accept: application/json

Authorization: Bearer {token}

Transfered parameters:

Parameter	Value
accountId	Identifier of user (advertising agency) account
client_id	Advertising agency client id
account_type	Account used for filling up should be one of values: personal or bonus
transfer_amount	Amount in advertising agency currency should be numeric
Returned answer:

{
    "idAuth":"_identifier_of_user's_account__",
       "clientId":"_client_id_",
      "status":"success",
     "bonus\personal_account":"_accout_balance_",
   bonus or personal based on incoming parameters,
      "wallet":{
       "balance":"_client's_account_balance_",

   }
}
All sums transfered in advertising agency currency.

Possible errors:

1) If money on the specified account is not enough, the amount entered in the transferred data is larger than the specified purse, return the error "The amount of money in the account is less than what you are trying to transfer."

2) If the transferred current token is invalid, returned error is "invalid token"

3) If the client id is not in the system or curator is not this advertising agency, return error "Invalid client id"

4) If the account, client, and the amount of remittances are empty, return the error "Account (client, amount) is not specified "