# MediaSmart API — Documentação Oficial Completa

> **Manutenção:** Tier 3 — revisão quando o vendor mudar a API.

> Salvo em: 2026-06-11 por Douglas (colado da documentação oficial)
> Fonte: https://api.mediasmart.io
> Status: ✅ COMPLETA — documento original sem modificações abaixo desta linha
> Ver também: `api_capabilities.md` — resumo das capacidades relevantes para nosso ETL

---

Introduction
This document describes how to use Mediasmart API. All requests must be thrown against one of the following servers:

Production environment: https://api.mediasmart.io
Testing environment: http://apitest.mediasmart.io
In this document, we’ll use the production domain for all examples, but keep in mind they are separated environments, with different users and data.

Public routes
First level routes are public. This means that no authorization is required to use them.

[GET] /status
A simple check to know if the server is running.

Success response:

Code	Meaning	Content
200	Success	-
Sample call:

$ curl -v 'https://api.mediasmart.io/status'

> GET /status HTTP/1.1
> Host: api.mediasmart.io
> User-Agent: curl/7.43.0
> Accept: */*
>
< HTTP/1.1 200 OK
...
Authentication
All private routes start with /api/... prefix. To use them you’ll need to attach an Authorization header containing a valid token. To obtain a token, you should use the public login endpoint.

[POST] /login
This allows you to obtain an authentication token from a known username and password. All private routes expect that token, attached in the Authorization header.

Body params

Field	Scope	Type	Description
username	required	string	Your username
password	required	string	Your password
Success response

Code	Meaning	Content
200	Success	An authentication context, including a token and some user data
Error response

Code	Meaning
401	Not authorized.
Sample call

$ curl -X POST \
       -d username=<your_username> -d password=<your_password> \
       'https://api.mediasmart.io/login'

{
  "token": "<auth_token>",
  "expired_at": "<iso_date>",
  "username": "<login_username>",
  "name": "<your_email>"
  "email": "<your_email_address>",
  ...
  "organization": {
    "name": "<organization_name>",
    "currency": "<eur|gbr|usd>",
    ...
  }
}
Dictionary
Our API offers some dictionaries, useful to know available values for all variables.

[GET] /api/dictionary
Retrieves the main dictionary containing main constants:

Success response:

Code	Meaning	Content
200	Success	Dictionary object: {attr1: {...}, attr2: {...}}
Error response:

Code	Meaning
401	Not authorized.
Sample call:

$ curl 'https://api.mediasmart.io/api/dictionary' \
       -H 'Authorization: <token>'

{
  countries: {...},
  iab_categories: {...},
  publisher_categories: {...},
  exchanges: {...},
  kpis: {...},
  creative_sizes: {...},
  currencies: {...},
  drilldown: {...},
  daystats_kpis: {...},
  display_position: {...},
  goal_kpis: {...},
  operating_systems: {...},
  ...
}
[GET] /api/dictionary/countries
Retrieves all available countries for reporting or campaigns configuration:

Success response:

Code	Meaning	Content
200	Success	Plain object: {attr1: 'x', attr2: 'y', ...}
Error response:

Code	Meaning
401	Not authorized.
Sample call:

$ curl 'https://api.mediasmart.io/api/dictionary/countries' \
       -H 'Authorization: <token>'

{
  "URY" : "Uruguay",
  "CUB" : "Cuba",
  "VNM" : "Vietnam",
  "ASM" : "American Samoa",
  "EGY" : "Egypt",
  ...
}
[GET] /api/dictionary/regions
Retrieves all available regions from specified countries list.

URL params:

Field	Scope	Type	Description
countries	optional	list	Countries to filter: ?countries=ESP,FRA
Success response:

Code	Meaning	Content
200	Success	Plain object: {attr1: 'x', attr2: 'y', ...}
Error response:

Code	Meaning
401	Not authorized.
Sample call:

$ curl 'https://api.mediasmart.io/api/dictionary/regions?countries=ESP,FRA' \
       -H 'Authorization: <token>'

{
  "FRA:F" : "Centre",
  "ESP:GA" : "Galicia",
  "ESP:CM" : "Castille-La Mancha",
  "FRA:P" : "Lower Normandy",
  ...
}
[GET] /api/dictionary/cities
Retrieves all available cities from specified countries or regions list.

URL params:

Field	Scope	Type	Description
countries	optional	list	Countries to filter: ?countries=ESP,FRA
regions	optional	list	Regions to filter: ?regions=ESP:GA,FRA:P
Success response:

Code	Meaning	Content
200	Success	Plain object: {attr1: 'x', attr2: 'y', ...}
Error response:

Code	Meaning
401	Not authorized.
Sample call:

$ curl 'https://api.mediasmart.io/api/dictionary/cities?regions=ESP:AS' \
       -H 'Authorization: <token>'

{
  "3121424" : "Gijón",
  "3110962" : "Sama",
  "3129135" : "Avilés",
  "3116789" : "Mieres",
  "3114711" : "Oviedo",
  ...
}
[GET] /api/dictionary/mosaic
Retrieves all available mosaic profiles from specified countries.

URL params:

Field	Scope	Type	Description
countries	optional	list	Countries to filter: ?countries=ESP,FRA
Success response:

Code	Meaning	Content
200	Success	Plain object: {attr1: 'x', attr2: 'y', ...}
Error response:

Code	Meaning
401	Not authorized.
Sample call:

$ curl 'https://api.mediasmart.io/api/dictionary/mosaic?countries=ESP' \
       -H 'Authorization: <token>'

{
  esp:a:01: "Spain A01 :: Elites > Classic Elites",
  esp:a:02: "Spain A02 :: Elites > Urban Elites",
  esp:a:03: "Spain A03 :: Elites > Residential Elites",
  ...
}
[GET] /api/dictionary/audiences
Retrieves all available audiences in your account DMP. The result is a map where the key is the audience code and the value is the number of devices its audience has loaded today. Your account DMP is based on the organization bound to the authorization credentials. Audiences that were loaded in the past but are now empty will list zero elements.

Success response:

Code	Meaning	Content
200	Success	A map of loaded audiences for your DMP
Error response:

Code	Meaning
401	Not authorized. Rejected token.
Sample call:

$ curl 'https://api.mediasmart.io/api/dictionary/audiences'
       -H 'Authorization: <token>'

{
  "audience1": 0,
  "audience2": 42,
  "other_audience_code": 333
}
NOTE: See DMP Audiences

Analytics
[GET] /api/analytics/summary/:kpi
Retrieves a general view of the evolution of user’s campaigns, during the last week, based on a provided KPI. :kpi must be one of the following:

wonprice
cpm
cpc
cpa1, cpa2…
URL params:

Field	Scope	Type	Description	Example
campaigns	optional	list	Campaign identifiers to consider	campaigns=id1,id2,id3
If no campaigns are filtered, then a single timeline is returned for all campaigns.

Success response:

Code	Meaning	Content
200	Success	One or more timelines
Error response:

Code	Meaning
401	Not authorized. Rejected token.
400	Bad request.
Sample call:

$ curl 'https://api.mediasmart.io/api/analytics/summary/cpc \
       ?campaigns=id1,id2,id3' \
       -H 'Authorization: <token>'

{
   "id1" : {
      "2015-10-09" : "0.07",
      "2015-10-10" : "0.07",
      ...
   },
   "id2" : {
      "2015-10-09" : "0.10",
      "2015-10-10" : "0.08",
      ...
   },
   ...
}
[GET] /api/analytics/summary/limits/:kpi
Returns recent limits status for your campaigns. :kpi must be one of the following:

wonprice
impressions
clicks
URL params:

Field	Scope	Type	Description	Example
campaigns	optional	list	Campaign identifiers to consider	campaigns=id1,id2,id3
Success response:

Code	Meaning	Content
200	Success	Grouped timelines: {expected: {...}, observed: {...}, global: {...}}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
400	Bad request.
Sample call:

$ curl 'https://api.mediasmart.io/api/analytics/summary/limits/impressions' \
       -H 'Authorization: <token>'

{
   "expected" : {
      "2015-10-09" : "46333.33",
      "2015-10-13" : "30250.00",
      ...
   },
   "observed" : {
      "2015-10-10" : "30060.00",
      "2015-10-12" : "32844.00",
      ...
   },
   "global" : {
      "time" : 30,
      "delivery" : 25
   }
}
[GET] /api/analytics/summary/goals/:kpi
Retrieves a summary about pricing goals, both expected and observed values. :kpi must be one of the following:

cpm
cpv
cpc
cpa1, cpa2…
URL params:

Field	Scope	Type	Description	Example
campaigns	optional	list	Campaign identifiers to consider	campaigns=id1,id2,id3
Success response:

Code	Meaning	Content
200	Success	Grouped timelines: {expected: {...}, observed: {...}}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
400	Bad request.
Sample call:

$ curl 'https://api.mediasmart.io/api/analytics/summary/goals/cpa1' \
       -H 'Authorization: <token>'

{
   "observed" : {
      "2015-10-13" : "13.08",
      "2015-10-14" : "7.70",
      ...
   },
   "expected" : {
      "2015-10-09" : "1.21",
      "2015-10-10" : "3.35",
      ...
   }
}
[GET] /api/analytics/drilldown/:variable
Compute the drilldown of a single variable, where :variable must be any available drilldown variable.

All drilldown variables are defined in the dictionary, as drilldown:

abtag : Strategy Name (historical)
adsquareconfigid : Adsquare Audience ID
adstxt : Ads.txt Publishers
advertiser : Advertiser Domain
advertiserdescription : Advertiser Name
agegroup : Age
app_bundle : Promoted application bundle
apprating : App Store Rating
auctiontype : Auction Type
audience_name : Audience Name
browser : Browser
bundleid : Bundle ID
campaign : Campaign
campaignname : Campaign Name (historical)
carrier : Mobile operator
category : Audience
city : City
client_currency : Currency of client
controlid : Campaign ID
convsource : Conversion source
costsource : Other Cost Source
countrycode : Country
creaid : Creative ID
creative : Creative
creativeid : Campaign Creative ID
creativename : Creative Name (historical)
creativetype : Creative Type
day : Day
dayoftheweek : Day of the week
deal_name : Deal Name
deal : Deal
devicetype : Device type
displaymanager : Display Manager
dmv : Display Manager Version
dnt : Do Not Track
domain : Publisher Domain
exchange : Ad Exchange
extendedconnectiontype: Connection type
extendeddevicetype : Connected Device
gender : Gender
georegion_areaid : Area ID
georegion_areaname : Area Name
hashouseholdid : Household ID
hasidl : Has RampID
hasmaxawareness : Has Max User Awareness
hasmediasmartid : Has mediasmart ID
hour : Hour
iab_categories : Advertirser IAB Category
iabcategory : IAB Category
iabsubcategory : IAB Subcategory
identitysolution : Identity Solution Used
idtype : ID Type
interstitial : Interstitial
isp : ISP
locationtype : Location precision
make : Make
model : Model
month : Month
nativesize : Native Size
organization : Organization
organizationid : Organization ID
os : Operating system
osversion : Operating system version
peer39context : Peer39 Context
peer39contextids : Peer39 Context IDs
placebo : Creative vs. Placebo
pricefloor : Price floor
publisher_id : Publisher ID (deprecated)
publisher_name : Publisher Name (deprecated)
publisher : Publisher (deprecated)
publishercompany : Publisher Company
publisherid : Publisher ID
publisherkeyword : Publisher Keyword
publishername : Publisher Name
publisherurl : Publisher URL
revenuesource : Revenue Source
seat_id : Seat ID
simcountrycode : Country of SIM
size : Size
skappattribution : SKAD Attribution
skcompatible : SKAD Network enabled
skeventnum : SKAD Events
skreinstall : SKAD Reinstall
skview : SKAD View / Storekit
source : App vs. Web
strategyid : Strategy ID
strategyname : Strategy
tagid : Tag ID
trackingtool : Tracking Tool
userlanguage : Language
weathercontextname : Weather Conditions
week : Week
URL parameters

Field	Scope	Type	Description	Example
from	required	date	First day to consider	from=2015-02-23
to	required	date	Last day to consider	to=2015-02-23
kpis	required	list	KPIs to get	kpis=cpm,cpc
limit	optional	number	Max number of results (25 by default)	limit=50
rules	optional	list	Fixed filters	rules=countrycode=[ESP,FRA];os=[android]
raw	optional	boolean	Retrieve raw data. Don’t round numbers	raw=true
All available kpis are defined in the dictionary, as kpis:

adsquarecost: Ad Square Cost
auctioncharge: Auction Charge
convertedadsquarecost: Ad Square Cost in client currency
convertedothercost: Other Cost in client currency
offers: Bid offers
bids: Bids
bidpercent: Bid %
won: Won
wonpercent: Won %
usdcost: Cost in USD
convertedpartnercost: Partner cost in client currency
cimpressions: Impressions on companion ads
wonprice: Media Cost
dealcharge: Dealcharge
impressions: Impressions
impressionstotal: All Impressions (incl. Ghost Placebo)
clicks: Clicks
ctr: CTR
events1: Conversions 1
msevents1: MS Conversions 1
cr1: CR 1
events2: Conversions 2
msevents2: MS Conversions 2
cr2: CR 2
events3: Conversions 3
msevents3: MS Conversions 3
cr3: CR 3
events4: Conversions 4
msevents4: MS Conversions 4
cr4: CR 4
events5: Conversions 5
msevents5: MS Conversions 5
cr5: CR 5
cpm: CPM: Cost per Mille impressions
cpc: CPC: Cost per click
cpa1: CPA1: Cost per conversion 1
cpa2: CPA2: Cost per conversion 2
cpa3: CPA3: Cost per conversion 3
cpa4: CPA4: Cost per conversion 4
cpa5: CPA5: Cost per conversion 5
cpvcomplete: CPV Complete (per mille)
cpvstart: CPV Start (per mille)
bidprice: Total bids cost
techfee: Tech fee
ecpm: eCPM: Cost per Mille impressions + Tech fee
ecpc: eCPC: Cost per click + Tech fee
ecpa1: eCPA1: Cost per conversion 1 + Tech fee
ecpa2: eCPA2: Cost per conversion 2 + Tech fee
ecpa3: eCPA3: Cost per conversion 3 + Tech fee
ecpa4: eCPA4: Cost per conversion 4 + Tech fee
ecpa5: eCPA5: Cost per conversion 5 + Tech fee
timeToConversion1: Time to Conversion 1 (seconds)
timeToConversion2: Time to Conversion 2 (seconds)
timeToConversion3: Time to Conversion 3 (seconds)
timeToConversion4: Time to Conversion 4 (seconds)
timeToConversion5: Time to Conversion 5 (seconds)
assistedConversions1: Estimated Assisted Conversions 1
assistedConversions2: Estimated Assisted Conversions 2
assistedConversions3: Estimated Assisted Conversions 3
assistedConversions4: Estimated Assisted Conversions 4
assistedConversions5: Estimated Assisted Conversions 5
assistedRate1: Estimated Assisted Rate 1
assistedRate2: Estimated Assisted Rate 2
assistedRate3: Estimated Assisted Rate 3
assistedRate4: Estimated Assisted Rate 4
assistedRate5: Estimated Assisted Rate 5
othercost: Other cost
partnercost: Partner cost
clientrevenue: Event revenue
convertedclientrevenue: Event Revenue in client currency
videostart: Video start
videofirstquartile: Video 25% viewed
videomidpoint: Video 50% viewed
videothirdquartile: Video 75% viewed
videocomplete: Video complete
videocomplete: Video complete
videocomplete: Video complete
videocomplete: Video complete
videocomplete: Video complete
videocomplete: Video complete
views: Video views
vr_start: Video start rate
vr_firstquartile: Video 25% viewed rate
vr_midpoint: Video 50% viewed rate
vr_thirdquartile: Video 75% viewed rate
vr_complete: Video completed rate
incremental_conversions_1: Incremental Conversions 1
incremental_conversions_percent_1: Incremental Conversions1
uplift_1: Uplift 1
cpi1: CPI1: Cost Per Incremental Conversion 1
incremental_conversions_2: Incremental Conversions 2
incremental_conversions_percent_2: Incremental Conversions2
uplift_2: Uplift 2
cpi2: CPI2: Cost Per Incremental Conversion 2
incremental_conversions_3: Incremental Conversions 3
incremental_conversions_percent_3: Incremental Conversions3
uplift_3: Uplift 3
cpi3: CPI3: Cost Per Incremental Conversion 3
incremental_conversions_4: Incremental Conversions 4
incremental_conversions_percent_4: Incremental Conversions4
uplift_4: Uplift 4
cpi4: CPI4: Cost Per Incremental Conversion 4
incremental_conversions_5: Incremental Conversions 5
incremental_conversions_percent_5: Incremental Conversions5
uplift_5: Uplift 5
cpi5: CPI5: Cost Per Incremental Conversion 5
estimated_visits: Estimated visits
exposed_percent: Exposed %
uplift: Uplift factor
attributed_visits: Attributed visits
visits: Observed visits
organic_visits: Organic visits
incremental_visits: Incremental visits
incremental_visit_percent: Incremental visit %
client_cost: Final Price
margin: Margin
margin_percentage: Margin %
aderror: Ad Error
aderrorpercent: Ad Error %
adloaded: Ad Loaded
adloadedpercent: Ad Loaded %
adviewed: Ad Viewed
adviewedpercent: Ad Viewed %
skevents: Total sum of post install events, not counting installs
skinstalls: SKAdNetwork received installs
Success response:

Code	Meaning	Content
200	Success	A drilldown map for each requested KPI: {cpm: {...}, cpc: {...}, ...}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden.
400	Wrong request.
Sample call:


$ curl 'https://api.mediasmart.io/api/analytics/drilldown/day \
        ?from=2016-01-01 \
        &to=2016-01-10 \
        &kpis=impressions,clicks,cpm \
        &rules=os=\[android,blackberry\];countrycode=\[ESP,FRA\]' \
        -H 'Authorization: <token>'

{
   "cpm" : {
      "2016-01-01" : "0.78",
      "2016-01-02" : "0.79",
      "2016-01-03" : "0.74"
      ...
   },
   "impressions" : {
      "2016-01-01" : "7604605",
      "2016-01-02" : "7037341",
      "2016-01-03" : "7381303",
      ...
   },
   "clicks" : {
      "2016-01-01" : "101103",
      "2016-01-02" : "99406",
      "2016-01-03" : "94051",
      ...
  },
}
[GET] /api/analytics/custom-report
Download a full report, drilling down for some criteria and limited to a provided time range.

URL parameters:

Field	Scope	Type	Description	Example
from	required	date	First day to consider	from=2015-02-23
to	required	date	Last day to consider	to=2015-02-23
drilldown	required	list	Drilldown variables to get	drilldown=exchange,os
kpis	optional	list	KPIs to retrieve	kpis=impressions,clicks
format	optional	string	File format: excel, csv	format=excel
rules	optional	list	Fixed filters	rules=countrycode=[ESP,FRA];os=[android]
raw	optional	boolean	Retrieve raw data. Don’t round numbers	raw=true
All drilldown variables are defined in the dictionary, as drilldown:

abtag : Strategy Name (historical)
adserverpartnerorgid : Partner (adserver)
adsquareconfigid : Adsquare Audience ID
adstxt : Ads.txt Publishers
advertiser : Advertiser Domain
advertiserdescription : Advertiser Name
agegroup : Age
app_bundle : Promoted application bundle
apprating : App Store Rating
auctiontype : Auction Type
audience_name : Audience Name
browser : Browser
bundleid : Bundle ID
campaign : Campaign
campaignname : Campaign Name (historical)
carrier : Mobile operator
category : Audience
city : City
client_currency : Currency of client
controlid : Campaign ID
convsource : Conversion source
costsource : Other Cost Source
countrycode : Country
creaid : Creative ID
creative : Creative
creativeid : Campaign Creative ID
creativename : Creative Name (historical)
creativetype : Creative Type
day : Day
dayoftheweek : Day of the week
deal : Deal
deal_name : Deal Name
devicetype : Device type
dmv : Display Manager Version
dnt : Do Not Track
domain : Publisher Domain
eventid : Event ID
exchange : Ad Exchange
extendedconnectiontype: Connection type
extendeddevicetype : Connected Device
filtertype : Filter Type
gender : Gender
georegion_areaid : Area ID (only for geolocated campaigns with named areas)
georegion_areaname : Area Name (only for geolocated campaigns with named areas)
hashouseholdid : Household ID
hasmediasmartid : mediasmart ID
hour : Hour
iab_categories : Advertirser IAB Category
iabcategory : IAB Category
iabsubcategory : IAB Subcategory
idtype : ID Type
interstitial : Interstitial
isp : ISP
locationtype : Location precision
metricspartnerorgid : Partner (metrics)
month : Month
nativesize : Native Size
organization : Organization
organizationid : Organization ID
os : Operating system
osversion : Operating system version
placebo : Creative vs. Placebo
pricefloor : Price floor
publisher : Publisher (deprecated)
publisher_id : Publisher ID (deprecated)
publisher_name : Publisher Name (deprecated)
publishercompany : Publisher Company
publisherid : Publisher ID
publisherkeyword : Publisher Keyword
publishername : Publisher Name
publisherurl : Publisher URL
revenuesource : Revenue Source
seat_id : Seat ID
simcountrycode : Country of SIM
size : Size
skappattribution : SKAD Attribution
skcompatible : SKAD Network enabled
skeventnum : SKAD Events
skreinstall : SKAD Reinstall
skview : SKAD View / Storekit
source : App vs. Web
strategyid : Strategy ID
strategyname : Strategy
tagid : Tag ID
trackingtool : Tracking Tool
userlanguage : Language
week : Week
All available kpis are defined in the dictionary, as kpis:

adsquarecost: Ad Square Cost
auctioncharge: Auction Charge
convertedadsquarecost: Ad Square Cost in client currency
convertedothercost: Other Cost in client currency
offers: Bid offers
bids: Bids
bidpercent: Bid %
won: Won
wonpercent: Won %
usdcost: Cost in USD
convertedpartnercost: Partner cost in client currency
cimpressions: Impressions on companion ads
wonprice: Media Cost
dealcharge: Dealcharge
impressions: Impressions
impressionstotal: All Impressions (incl. Ghost Placebo)
clicks: Clicks
ctr: CTR
events1: Conversions 1
msevents1: MS Conversions 1
cr1: CR 1
events2: Conversions 2
msevents2: MS Conversions 2
cr2: CR 2
events3: Conversions 3
msevents3: MS Conversions 3
cr3: CR 3
events4: Conversions 4
msevents4: MS Conversions 4
cr4: CR 4
events5: Conversions 5
msevents5: MS Conversions 5
cr5: CR 5
cpm: CPM: Cost per Mille impressions
cpc: CPC: Cost per click
cpa1: CPA1: Cost per conversion 1
cpa2: CPA2: Cost per conversion 2
cpa3: CPA3: Cost per conversion 3
cpa4: CPA4: Cost per conversion 4
cpa5: CPA5: Cost per conversion 5
cpvcomplete: CPV Complete (per mille)
cpvstart: CPV Start (per mille)
bidprice: Total bids cost
techfee: Tech fee
ecpm: eCPM: Cost per Mille impressions + Tech fee
ecpc: eCPC: Cost per click + Tech fee
ecpa1: eCPA1: Cost per conversion 1 + Tech fee
ecpa2: eCPA2: Cost per conversion 2 + Tech fee
ecpa3: eCPA3: Cost per conversion 3 + Tech fee
ecpa4: eCPA4: Cost per conversion 4 + Tech fee
ecpa5: eCPA5: Cost per conversion 5 + Tech fee
timeToConversion1: Time to Conversion 1 (seconds)
timeToConversion2: Time to Conversion 2 (seconds)
timeToConversion3: Time to Conversion 3 (seconds)
timeToConversion4: Time to Conversion 4 (seconds)
timeToConversion5: Time to Conversion 5 (seconds)
assistedConversions1: Estimated Assisted Conversions 1
assistedConversions2: Estimated Assisted Conversions 2
assistedConversions3: Estimated Assisted Conversions 3
assistedConversions4: Estimated Assisted Conversions 4
assistedConversions5: Estimated Assisted Conversions 5
assistedRate1: Estimated Assisted Rate 1
assistedRate2: Estimated Assisted Rate 2
assistedRate3: Estimated Assisted Rate 3
assistedRate4: Estimated Assisted Rate 4
assistedRate5: Estimated Assisted Rate 5
othercost: Other cost
partnercost: Partner cost
clientrevenue: Event revenue
convertedclientrevenue: Event Revenue in client currency
videostart: Video start
videofirstquartile: Video 25% viewed
videomidpoint: Video 50% viewed
videothirdquartile: Video 75% viewed
videocomplete: Video complete
videocomplete: Video complete
videocomplete: Video complete
videocomplete: Video complete
videocomplete: Video complete
videocomplete: Video complete
views: Video views
vr_start: Video start rate
vr_firstquartile: Video 25% viewed rate
vr_midpoint: Video 50% viewed rate
vr_thirdquartile: Video 75% viewed rate
vr_complete: Video completed rate
incremental_conversions_1: Incremental Conversions 1
incremental_conversions_percent_1: Incremental Conversions1
uplift_1: Uplift 1
cpi1: CPI1: Cost Per Incremental Conversion 1
incremental_conversions_2: Incremental Conversions 2
incremental_conversions_percent_2: Incremental Conversions2
uplift_2: Uplift 2
cpi2: CPI2: Cost Per Incremental Conversion 2
incremental_conversions_3: Incremental Conversions 3
incremental_conversions_percent_3: Incremental Conversions3
uplift_3: Uplift 3
cpi3: CPI3: Cost Per Incremental Conversion 3
incremental_conversions_4: Incremental Conversions 4
incremental_conversions_percent_4: Incremental Conversions4
uplift_4: Uplift 4
cpi4: CPI4: Cost Per Incremental Conversion 4
incremental_conversions_5: Incremental Conversions 5
incremental_conversions_percent_5: Incremental Conversions5
uplift_5: Uplift 5
cpi5: CPI5: Cost Per Incremental Conversion 5
estimated_visits: Estimated visits
exposed_percent: Exposed %
uplift: Uplift factor
attributed_visits: Attributed visits
visits: Observed visits
organic_visits: Organic visits
incremental_visits: Incremental visits
incremental_visit_percent: Incremental visit %
client_cost: Final Price
margin: Margin
margin_percentage: Margin %
aderror: Ad Error
aderrorpercent: Ad Error %
adloaded: Ad Loaded
adloadedpercent: Ad Loaded %
adviewed: Ad Viewed
adviewedpercent: Ad Viewed %
skevents: Total sum of post install events, not counting installs
skinstalls: SKAdNetwork received installs
Success response:

Code	Meaning	Content
200	Success	A report file, CSV by default
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden.
400	Wrong request.
Sample call:

$ curl 'https://api.mediasmart.io/api/analytics/custom-report? \
        from=2015-10-13&to=2015-10-14 \
        &drilldown=day,exchange,os \
        &kpis=impressions,clicks' \
        &rules=countrycode=\[ESP,FRA\];os=\[android\]' \
       -H 'Authorization: <token>'

"2015-10-13","smartad","android","968492","6770"
"2015-10-13","mopub","android","900804","13656"
"2015-10-14","smartad","android","960925","20872"
...
[GET] /api/analytics/kpi/:kpi
Retrieves the evolution of a KPI during the last week, where :kpi is one of the available KPIs, defined in the dictionary, as kpis:

adsquarecost: Ad Square Cost
auctioncharge: Auction Charge
convertedadsquarecost: Ad Square Cost in client currency
convertedothercost: Other Cost in client currency
offers: Bid offers
bids: Bids
bidpercent: Bid %
won: Won
wonpercent: Won %
usdcost: Cost in USD
convertedpartnercost: Partner cost in client currency
cimpressions: Impressions on companion ads
wonprice: Media Cost
dealcharge: Dealcharge
impressions: Impressions
impressionstotal: All Impressions (incl. Ghost Placebo)
clicks: Clicks
ctr: CTR
events1: Conversions 1
msevents1: MS Conversions 1
cr1: CR 1
events2: Conversions 2
msevents2: MS Conversions 2
cr2: CR 2
events3: Conversions 3
msevents3: MS Conversions 3
cr3: CR 3
events4: Conversions 4
msevents4: MS Conversions 4
cr4: CR 4
events5: Conversions 5
msevents5: MS Conversions 5
cr5: CR 5
cpm: CPM: Cost per Mille impressions
cpc: CPC: Cost per click
cpa1: CPA1: Cost per conversion 1
cpa2: CPA2: Cost per conversion 2
cpa3: CPA3: Cost per conversion 3
cpa4: CPA4: Cost per conversion 4
cpa5: CPA5: Cost per conversion 5
cpvcomplete: CPV Complete (per mille)
cpvstart: CPV Start (per mille)
bidprice: Total bids cost
techfee: Tech fee
ecpm: eCPM: Cost per Mille impressions + Tech fee
ecpc: eCPC: Cost per click + Tech fee
ecpa1: eCPA1: Cost per conversion 1 + Tech fee
ecpa2: eCPA2: Cost per conversion 2 + Tech fee
ecpa3: eCPA3: Cost per conversion 3 + Tech fee
ecpa4: eCPA4: Cost per conversion 4 + Tech fee
ecpa5: eCPA5: Cost per conversion 5 + Tech fee
timeToConversion1: Time to Conversion 1 (seconds)
timeToConversion2: Time to Conversion 2 (seconds)
timeToConversion3: Time to Conversion 3 (seconds)
timeToConversion4: Time to Conversion 4 (seconds)
timeToConversion5: Time to Conversion 5 (seconds)
assistedConversions1: Estimated Assisted Conversions 1
assistedConversions2: Estimated Assisted Conversions 2
assistedConversions3: Estimated Assisted Conversions 3
assistedConversions4: Estimated Assisted Conversions 4
assistedConversions5: Estimated Assisted Conversions 5
assistedRate1: Estimated Assisted Rate 1
assistedRate2: Estimated Assisted Rate 2
assistedRate3: Estimated Assisted Rate 3
assistedRate4: Estimated Assisted Rate 4
assistedRate5: Estimated Assisted Rate 5
othercost: Other cost
partnercost: Partner cost
clientrevenue: Event revenue
convertedclientrevenue: Event Revenue in client currency
videostart: Video start
videofirstquartile: Video 25% viewed
videomidpoint: Video 50% viewed
videothirdquartile: Video 75% viewed
videocomplete: Video complete
videocomplete: Video complete
videocomplete: Video complete
videocomplete: Video complete
videocomplete: Video complete
videocomplete: Video complete
views: Video views
vr_start: Video start rate
vr_firstquartile: Video 25% viewed rate
vr_midpoint: Video 50% viewed rate
vr_thirdquartile: Video 75% viewed rate
vr_complete: Video completed rate
incremental_conversions_1: Incremental Conversions 1
incremental_conversions_percent_1: Incremental Conversions1
uplift_1: Uplift 1
cpi1: CPI1: Cost Per Incremental Conversion 1
incremental_conversions_2: Incremental Conversions 2
incremental_conversions_percent_2: Incremental Conversions2
uplift_2: Uplift 2
cpi2: CPI2: Cost Per Incremental Conversion 2
incremental_conversions_3: Incremental Conversions 3
incremental_conversions_percent_3: Incremental Conversions3
uplift_3: Uplift 3
cpi3: CPI3: Cost Per Incremental Conversion 3
incremental_conversions_4: Incremental Conversions 4
incremental_conversions_percent_4: Incremental Conversions4
uplift_4: Uplift 4
cpi4: CPI4: Cost Per Incremental Conversion 4
incremental_conversions_5: Incremental Conversions 5
incremental_conversions_percent_5: Incremental Conversions5
uplift_5: Uplift 5
cpi5: CPI5: Cost Per Incremental Conversion 5
estimated_visits: Estimated visits
exposed_percent: Exposed %
uplift: Uplift factor
attributed_visits: Attributed visits
visits: Observed visits
organic_visits: Organic visits
incremental_visits: Incremental visits
incremental_visit_percent: Incremental visit %
client_cost: Final Price
margin: Margin
margin_percentage: Margin %
aderror: Ad Error
aderrorpercent: Ad Error %
adloaded: Ad Loaded
adloadedpercent: Ad Loaded %
adviewed: Ad Viewed
adviewedpercent: Ad Viewed %
skevents: Total sum of post install events, not counting installs
skinstalls: SKAdNetwork received installs
URL params:

Field	Scope	Type	Description	Example
campaigns	optional	list	Campaign identifiers	campaigns=a,b,c
Success response:

Code	Meaning	Content
200	Success	Timeline
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden.
400	Wrong request.
Sample call:

$ curl 'https://api.mediasmart.io/api/analytics/kpi/clicks?campaigns=x,y,z'
       -H 'Authorization: <token>'

{
   "clicks" : {
      "2016-01-07" : 1115,
      "2016-01-06" : 1180,
      "2016-01-13" : 316,
      ...
   }
}
Analytics > Campaign
[GET] /api/campaign/:id/analytics/summary
Retrieves a simple summary of how a campaign is performing today, compared with the previous day. :id is a campaign identifier.

Success response:

Code	Meaning	Content
200	Success	Summary data
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaign/<identifier>/analytics/summary'
       -H 'Authorization: <token>'

{
 "clicks" : {
    "yesterday" : 137,
    "today" : 82
 },
 "events5" : {
    "yesterday" : 0,
    "today" : 0
 },
 "events2" : {
    "today" : 0,
    "yesterday" : 0
 },
 "offers" : {
    "today" : 23120,
    "yesterday" : 90310
 },
 "events1" : {
    "today" : 0,
    "yesterday" : 0
 },
 "impressions" : {
    "today" : 10517,
    "yesterday" : 30095
 },
 "events4" : {
    "yesterday" : 0,
    "today" : 0
 },
 "bids" : {
    "today" : 24642,
    "yesterday" : 92456
 },
 "events3" : {
    "yesterday" : 0,
    "today" : 0
 }
}
[GET] /api/campaign/:id/analytics/overview
Retrieves the overview section of the campaign dashboard.

Success response:

Code	Meaning	Content
200	Success	Overview data
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden.
404	Campaign or resource not found.
400	Campaign without Overview section. The campaign is valid but it has not overview data.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaign/<identifier>/analytics/overview'
       -H 'Authorization: <token>'

The format response is text (format csv).
[GET] /api/campaign/:id/analytics/kpi/:kpi
Retrieves the evolution of a KPI during the last week. It is a special version of this other endpoint. Read it for more info.

[GET] /api/campaign/:id/analytics/drilldown/:variable
Compute the drilldown of a single variable. It is a special version of this other endpoint. Read it for more info.

[GET] /api/campaign/:id/analytics/report
Download a full report, drilling down for some criteria and limited to a provided time range. It is a special version of this other endpoint. Read it for more info.

Analytics > Availability
[GET] /api/analytics/availability/drilldown/:variable
Retrieves an estimation of the available bidoffers for all possible values of a variable, where :variable the variable.

Available variables are defined in the dictionary, as availability_drilldown:

agegroup: Age
auctiontype: Auction type
audio: Creative Type: Audio
carrier: Mobile operator
countrycode: Country
day: Day
dayoftheweek: Day of the week
devicetype: Type of device
display: Display manager
dmv: Display manager version
dnt: Do Not Track
exchange: Exchange
extendedconnectiontype: Extended Connection Type
gender: Gender
geoAccuracy: Presence of Geo Accuracy
hasidl: Has RampID
hasmaxawareness: Has Max User Awareness
hour: Hour
iabcategory: IAB Category
iabsubcategory: IAB Subcategory
idfv: Pressence of IDFV
idtype: Type of user identifier
image: Creative Type: Image
interstitial: Interstitial
isp: ISP
javascript: Creative Type: 3rd party tag HTML
lastfix: Pressence of Lastfix
locationtype: Geolocation precision
make: Make
maxVast: Maximum version of VAST
maxduration: Maximum video duration
minVast: Minimum version of VAST
minduration: Minimum video duration
model: Model
native: Creative Type: Native
nativesize: Native size
omid: Support of OMID
omidver: Version of OMID
os: Operating system
osversion: Operating system version
pricefloor: Price floor
richmedia: Creative Type: 3rd party tag MRAID
simcountry: Sim country
size: Size
skcompatible: SK compatible
tagid: Tag id
typeofconsent: Type of consent
userlanguage: Language
video: Creative Type: Video/External Video
videoposition: Video position
videorewarded: Creative type: Video rewarded
vpaidVer: Version of VPAID
zeotap: Support of Zeotap ID+
URL params:

Field	Scope	Type	Description	Example
from	required	date	First day to consider	from=2015-02-23
to	required	date	Last day to consider	to=2015-02-23
rules	optional	list	Fixed values for some variables	rules=os=[android,iphone];countrycode=[ESP,FRA]
Success response:

Code	Meaning	Content
200	Success	An object with the amount of available impressions per variable value
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Permission denied.
400	Bad request.
Sample call:

$ curl 'https://api.mediasmart.io/api/analytics/availability/drilldown/os \
       ?from=2015-10-12 \
       &to=2015-10-13 \
       &rules=countrycode=\[ESP,FRA\]' \
       -H 'Authorization: <token>'

{
  android: 13232411,
  iphone: 442212,
  ...
}
[GET] /api/analytics/availability/summary
Retrieves an estimation of the amount of available bidoffers according with provided filters. This includes a total count and a timeline.

URL params:

Field	Scope	Type	Description	Example
from	required	date	First day to consider	from=2015-02-23
to	required	date	Last day to consider	to=2015-02-23
rules	optional	list	Fixed values for some variables	rules=os=[android,iphone];countrycode=[ESP,FRA]
Success response:

Code	Meaning	Content
200	Success	A number representing available bidoffers
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Permission denied.
400	Bad request.
Sample call:

$ curl 'https://api.mediasmart.io/api/analytics/availability/summary \
       ?from=2015-10-12 \
       &to=2015-10-13 \
       &rules=os=\[android,iphone\];countrycode=\[ESP,FRA\]' \
       -H 'Authorization: <token>'

{
  "count" : "11642975",
  "timeline" : {
     "13:00" : "454401",
     "14:00" : "704531",
     "15:00" : "394622",
     ...
  }
}
Analytics > Publishers
[GET] /api/analytics/publishers/drilldown/:variable
Computes the drilldown of a variable, according with some fixed filters, where :variable is the variable.

Available variables are defined in the dictionary, as publishers_drilldown:

agegroup: Age
auctiontype: Auction type
audio: Creative Type: Audio
bundleid: Bundle id
carrier: Mobile operator
connectiontype: Type of connection
consent: Consent
countrycode: Country
day: Day
dayoftheweek: Day of the week
devicetype: Type of device
display: Display manager
dmv: Display manager version
dnt: Do Not Track
domain: Domain
exchange: Exchange
extendedconnectiontype: Extended Connection Type
gender: Gender
geoAccuracy: Presence of Geo Accuracy
hasidl: Has RampID
hasmaxawareness: Has Max User Awareness
hour: Hour
iabcategory: IAB Category
iabsubcategory: IAB Subcategory
idfv: Pressence of IDFV
idtype: Type of user identifier
image: Creative Type: Image
interstitial: Interstitial
isp: ISP
javascript: Creative Type: 3rd party tag HTML
lastfix: Pressence of Lastfix
locationtype: Geolocation precision
make: Make
maxVast: Maximum version of VAST
maxduration: Maximum video duration
minVast: Minimum version of VAST
minduration: Minimum video duration
model: Model
native: Creative Type: Native
nativesize: Native size
omid: Support of OMID
omidver: Version of OMID
os: Operating system
osversion: Operating system version
pricefloor: Price floor
publisher: Publisher
publishercompany: Publisher company
publisherid: Publisher id
publisherkeyword: Publisher keyword
publishername: Publisher name
publisherurl: Publisher url
richmedia: Creative Type: 3rd party tag MRAID
simcountry: Sim country
size: Size
skcompatible: SK compatible
tagid: Tag id
typeofconsent: Type of consent
userlanguage: Language
video: Creative Type: Video/External Video
videoposition: Video position
videorewarded: Creative type: Video rewarded
vpaidVer: Version of VPAID
zeotap: Support of Zeotap ID+
URL params:

Field	Scope	Type	Description	Example
from	optional	date	Start date for the report	from=2015-04-12
to	optional	date	End date for the report	to=2015-04-15
rules	optional	list	Fixed values for some variables	rules=os=[android,iphone];countrycode=[ESP,FRA]
Success response:

Code	Meaning	Content
200	Success	An object containing bidoffers amount for each variable value
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Permission denied.
400	Bad request.
Sample call:

$ curl 'https://api.mediasmart.io/api/analytics/publishers/drilldown/os \
       ?rules=os=\[android,blackberry\];countrycode=\[ESP,FRA\]' \
       -H 'Authorization: <token>'

{
  "blackberry": 34332,
  "android": 7468823
}
[GET] /api/analytics/publishers
Retrieves a list of available publishers, according with some optional filters

URL params:

Field	Scope	Type	Description	Example
from	optional	date	Start date for the report	from=2015-04-12
to	optional	date	End date for the report	to=2015-04-15
rules	optional	list	Fixed values to filter	rules=os=[android,iphone];countrycode=[ESP,FRA]
limit	optional	number	The amount of items to retrieve	limit=10
offset	optional	number	An offset for the list	offset=29
Success response
Code	Meaning	Content
200	Success	A list of publishers info
Error response
Code	Meaning
401	Not authorized. Rejected token.
403	Permission denied.
Sample call
$ curl 'https://api.mediasmart.io/api/analytics/publishers \
       ?rules=os=\[android,blackberry\];countrycode=\[ESP,FRA\]' \
       -H 'Authorization: <token>'

[
  {
    "appsite" : "mobile.dailymotion.com",
    "url" : "",
    "keyword" : "mobiledailymotioncom",
    "publishertype" : "site",
    "publisher" : "",
    "offercount" : "1923064"
  },
  {
    "offercount" : "1909000",
    "keyword" : "leading_global_video_publisher_-_mw",
    "publishertype" : "site",
    "publisher" : "Leading Global Video Publisher",
    "appsite" : "Leading Global Video Publisher - MW",
    "url" : "dailymotion.com"
  },
  ...
]
Analytics > Real time
There is a way to obtain nearly real-time analytics, by mean of our “Daystats” tool.

[GET] /api/analytics/daystats
Computes a drilldown to extract all KPIs for possible values of a certain variable.

URL params:

Field	Scope	Type	Description	Example
from	optional	date	Start date for the drilldown, in YYYY-MM-DD format	from=2016-05-02
to	optional	date	End date for the drilldown, in YYYY-MM-DD format	to=2016-05-07
kpis	optional	list	List of KPIs to retrieve	kpis=won,wonpercent,bidcost,clicks
drilldown	mandatory	string	Variable to drilldown by	drilldown=exchange
campaign	optional	string	Fix a campaign	campaign=This_is_the_campaign_string
exchange	optional	string	Fix an AdExchange	exchange=mopub
keyword	optional	string	Fix a value for a keyword prefix	keyword=mopub
Available KPIs are defined in the dictionary, as daystats_kpis. Some of them are the following:

adloaded : Ad Loaded
adviewed : Ad Viewed
aderror : Ad Error
admarkupsize : Rendered bytes
bidprice : Total Bids Cost
clientrevenue : Event Revenue
prebids : Bid offers
bids : Bids
bidpercent : Bid percent (%)
won : Won
wonpercent : Won percentage of bids
bidcost : Media cost
serverscost : Network out cost
datacost : DMP Data Cost
bcpm : Bidding CPM
bcpc : Bidding CPC
bcpa, bcpa2, bcpa3, bcpa4, bcpa5 : Bidding CPA 1, 2, 3…
impressions : Amount of impressions
clicks : Amount of clicks
qclicks : Qualified Clicks
gclicks : Ghost Clicks
ctr : CTR
qctr : Qualified CTR
convs1, convs2, convs3…: Amount of conversions 1, 2, 3…
tconv1, tconv2, tconv3…: CR of conversion 1, 2, 3…
videostart : Video start
videofirstquartile : Video first quartile
videomidpoint : Video midpoint
videothirdquartile : Video third quartile
videocomplete : Video complete
views : Video views
vr_start : Video start rate
vr_firstquartile : Video 25% viewed rate
vr_midpoint : Video 50% viewed rate
vr_thirdquartile : Video 75% viewed rate
vr_complete : Video completed rate
skinstall : SKAdNetwork received installs
skevent : Total sum of post install events, not counting installs
Available variables are defined in the dictionary, as daystats_drilldown. Some of them are the following:

campaign : Campaign
day : Day
exchange : Ad Exchange
k:age : Age
k:cat : User interest
k:dmp:exp : Mosaic Info
k:gender : Gender
k:operator : Mobile operator
k:os : Operating system
k:simgeo : Sim Country
p:ab : Strategy
p:adsquare:aid : Adsquare ID
p:android:ver : Android version
p:areaid : Area ID
p:areaname : Area name
p:areatag : Area text
p:at : Auction Type
p:biddingslot : Bidding slot
p:browser : Browser
p:cat : Category on RTB
p:city : City
p:connectiontype: Connection Type (WiFi/Cellular)
p:conv : Conversion matching
p:convareaid : Conversion Area ID
p:convareaname : Conversion area name
p:convgeolistid : Conversion Geolist ID
p:creativename : Creative
p:creativetype : Creative Type
p:crsource : Revenue Source
p:deal : Deal
p:devicetype : Device type
p:dmver : Display Manager Version
p:dnt : Display Manager Version
p:eventid : EventID
p:exacthour : Hour of he day
p:geo : Geo Country
p:geolistid : Geolist ID
p:gzip:response : Gzip Response
p:hasmaxawareness: Has Max User Awareness
p:hasrampidp : Has RampID
p:hour : Hour range
p:householdid : Household ID
p:identitysolution: Identity Solution Used
p:idtype : Tracking ID type
p:instantplay : Instant Play Video
p:ios:ver : iOS version
p:iplist : IP List
p:isp : ISP
p:language : Language
p:loc : Geolocation
p:make : Make
p:mediasmartid : mediasmart ID
p:model : Model
p:native : Native size
p:nativebanner : Banner-style Native
p:org : Organization
p:peer : Peer39 Context ID
p:peername : Peer39 Context
p:pf : Price Floor
p:placebo : Placebo
p:pos : Page Placement
p:pricegap : Price Gap
p:proxy : System pub header
p:pub : Publisher
p:rtbfilter : System scan
p:rtbver : RTB Protocol Version
p:score:cpa : Logscore for CPA
p:score:cpc : Logscore for CPC
p:secure : Bid connection type
p:size : Size
p:skcompatible : SKAD Network enabled
p:skversion : SKAdNetwork version
p:sys : System A/B
p:tag : Tagid
p:tspan : Time span click to conv
p:type : App vs. Web
p:weather : Weather Conditions
p:week : Day of the week
p:zip : Zip
Example:

$ curl 'https://api.mediasmart.io/api/analytics/daystats \
       ?from=2016-06-10 \
       &to=2016-06-11 \
       &kpis=won,impressions,clicks \
       &drilldown=campaign \
       &keyword=k:gender:male \
       &exchange=mopub' \
       -H 'Authorization: <token>'

[
  {
     drillby: "Campaign Name X",
     won: 786,
     impressions: 759,
     clicks: 34
  },
  ...
]
[GET] /api/analytics/daystats-report
Downloads a drilldown report in CSV format. Check previous section for more details.

URL params:

Field	Scope	Type	Description	Example
from	optional	date	Start date for the drilldown, in YYYY-MM-DD format	from=2016-05-02
to	optional	date	End date for the drilldown, in YYYY-MM-DD format	to=2016-05-07
kpis	optional	list	List of KPIs to retrieve	kpis=won,wonpercent,bidcost,clicks
drilldown	mandatory	string	Variable to drilldown by	drilldown=exchange
campaign	optional	string	Fix a campaign	campaign=This_is_the_campaign_string
exchange	optional	string	Fix an AdExchange	exchange=mopub
keyword	optional	string	Fix a value for a keyword prefix	keyword=mopub
Available KPIs are defined in the dictionary, as daystats_kpis. Some of them are the following:

adloaded : Ad Loaded
adviewed : Ad Viewed
aderror : Ad Error
admarkupsize : Rendered bytes
bidprice : Total Bids Cost
clientrevenue : Event Revenue
prebids : Bid offers
bids : Bids
bidpercent : Bid percent (%)
won : Won
wonpercent : Won percentage of bids
bidcost : Media cost
serverscost : Network out cost
datacost : DMP Data Cost
bcpm : Bidding CPM
bcpc : Bidding CPC
bcpa, bcpa2, bcpa3, bcpa4, bcpa5 : Bidding CPA 1, 2, 3…
impressions : Amount of impressions
clicks : Amount of clicks
qclicks : Qualified Clicks
gclicks : Ghost Clicks
ctr : CTR
qctr : Qualified CTR
convs1, convs2, convs3…: Amount of conversions 1, 2, 3…
tconv1, tconv2, tconv3…: CR of conversion 1, 2, 3…
videostart : Video start
videofirstquartile : Video first quartile
videomidpoint : Video midpoint
videothirdquartile : Video third quartile
videocomplete : Video complete
views : Video views
vr_start : Video start rate
vr_firstquartile : Video 25% viewed rate
vr_midpoint : Video 50% viewed rate
vr_thirdquartile : Video 75% viewed rate
vr_complete : Video completed rate
skinstall : SKAdNetwork received installs
skevent : Total sum of post install events, not counting installs
Available variables are defined in the dictionary, as daystats_drilldown. Some of them are the following:

campaign : Campaign
day : Day
p:org : Organization
exchange : Ad Exchange
p:adsquare:aid : Adsquare ID
k:age : Age
p:android:ver : Android version
p:type : App vs. Web
p:areaid : Area ID
p:areatag : Area text
p:areaname : Area name
p:at : Auction Type
p:secure : Bid connection type
p:biddingslot : Bidding slot
p:cat : Category on RTB
p:city : City
p:connectiontype: Connection Type (WiFi/Cellular)
p:conv : Conversion matching
p:conv:areaid : Conversions per area id
p:conv:geolistid: Conversions per geolist id
p:creativename : Creative
p:creativetype : Creative Type
p:week : Day of the week
p:deal : Deal
p:devicetype : Device type
p:dmver : Display Manager Version
p:dnt : Display Manager Version
k:tail : Download profiles
p:eventid : EventID
k:gender : Gender
p:geo : Geo Country
p:geolistid : Geolist ID
p:loc : Geolocation
p:exacthour : Hour of he day
p:hour : Hour range
p:ios:ver : iOS version
p:instantplay : Instant Play Video
p:iplist : IP List
p:isp : ISP
p:language : Language
p:make : Make
k:operator : Mobile operator
p:model : Model
p:ios:mopub : Mopub iOS UA
k:dmp:exp : Mosaic Info
p:native : Native size
k:os : Operating system
p:placebo : Placebo
p:pretargeting : Pretargeting
p:pricecache : Price cache
p:pricegap : Price Gap
p:pf : Price Floor
p:pub : Publisher
p:refresh : Refresh
p:repeated : Repeated
k:isp : Residential ISP
k:plus : Retargeting on click
k:rplus : Retargeting on conversion
p:rtbver : RTB Protocol Version
k:simgeo : Sim Country
p:size : Size
p:ab : Strategy
p:proxy : System pub header
p:sys : System A/B
p:tag : Tagid
p:timetoclick : Time from bid to click
p:tspan : Time span click to conv
p:idtype : Tracking ID type
k:profile : User profile
k:cat : User interest
p:zip : Zip
p:score:cpc : Logscore for CPC
p:score:cpa : Logscore for CPA
p:rtbfilter : System scan
p:crsource : Revenue Source
p:gzip:response : Gzip Response
p:nativebanner : Banner-style Native
p:skcompatible : SKAD Network enabled
p:pos : Page Placement
p:browser : Browser
p:householdid : Household ID
p:mediasmartid : mediasmart ID
Example:

$ curl 'https://api.mediasmart.io/api/analytics/daystats-report \
       ?from=2016-06-10 \
       &to=2016-06-11 \
       &kpis=won,impressions,clicks \
       &drilldown=campaign \
       &keyword=k:gender:male \
       &exchange=mopub' \
       -H 'Authorization: <token>'

"Value", "Won", "Impressions", "Clicks"
"Campaign Name string A", "1234", "323", "45"
"Campaign Name string B", "9234", "923", "69"
"Campaign Name string C", "7634", "523", "85"
...
NOTE Values used to fix campaign URL param must be extracted from a drilldown by that variable. This means that you cannot use Campaign identifiers, but a string derived from the name. The same applies to keyword or exchange parameters. To know possible values to fix you’ll probably need to do a previous drilldown.

Advertiser
The following routes let you manage your advertisers.

[GET] /api/advertisers
Retrieves all existing advertisers in an organization.

Success response:

Code	Meaning	Content
200	Success	An array of objects: [{attr1: 'x', attr2: 'y', ...}]
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call


    {
        "event_id": "mediasmart-xxt70yvxx1qfgglzxduqx7idqeo571we",
        "domain": "test.com",
        "iab_category": "IAB8",
        "id": "xxt70yvxx1qfgglzxduqx7idqeo571we",
        "name": "Test advertiser",
        "sensitive_content": false
    }
[POST] /api/advertiser
Creates a new advertiser.

Body params:

Field	Scope	Type	Description	Example
name	required	string	Name for humans	{..., name: 'test advertiser', ...}
domain	required	string	Domain of the advertiser	{..., domain: 'test.com' ...}
iab_category	required	string	IAB cateogry describing the advertiser	{..., iab_category: 'IAB8', ...}
advertiser_domain	required	string	the advertisers domain	{..., advertiser_domain: "mediasmart.es", ...}
sensitive_content	optional	boolean	Is the content of the advertiser sensitive? Gambling, Alcohol, etc.	{..., "sensitive_content": false, ...}
Available IAB categories are defined the dictionary:

IAB1: Arts & Entertainment
IAB2: Automotive
IAB2-1: Automotive > Auto Parts
…
Success response:

Code	Meaning	Content
200	Success	The advertiser is created
{
    "event_id": "mediasmart-xxt70yvxx1qfgglzxduqx7idqeo571we",
    "domain": "test.com",
    "iab_category": "IAB8",
    "id": "xxt70yvxx1qfgglzxduqx7idqeo571we",
    "name": "Test advertiser",
    "sensitive_content": false
},`
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
[PUT] /api/advertiser:is
Updates advertiser properties, where :id is the advertiser identifier.

Body params:

Field	Scope	Type	Description	Example
name	required	string	Name for humans	{..., name: 'test advertiser', ...}
domain	required	string	Domain of the advertiser	{..., domain: 'test.com' ...}
iab_category	required	string	IAB cateogry describing the advertiser	{..., iab_category: 'IAB8', ...}
advertiser_domain	required	string	the advertisers domain	{..., advertiser_domain: "mediasmart.es", ...}
sensitive_content	optional	boolean	Is the content of the advertiser sensitive? Gambling, Alcohol, etc.	{..., "sensitive_content": false, ...}
Success response:

Code	Meaning	Content
200	Success	The updated advertiser model: {id: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
404	Not found.
[DELETE] /api/advertiser:id
Removes an advertiser from an organization, where :id is the advertiser identifier to be removed.

Success response:

Code	Meaning	Content
200	Success	The removed advertiser model: {id: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
404	Not found.
Campaigns
The following routes let you manage your campaigns.

[GET] /api/campaigns
List current campaigns. For performance optimizations, only a summary (with some metadata) for each campaign is returned, not the whole campaign body.

URL params:

Field	Scope	Type	Description	Example
state	optional	string	Campaign state	state=active
Available states are defined in the dictionary. They are self-descriptive:

active
inactive
deleted
preview
Success response:

Code	Meaning	Content
200	Success	A list of campaign summaries: [{...}, {...}, ...]
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaigns?state=active' \
       -H 'Authorization: <token>'

[
  {
    id: X,
    name: 'Bla bla bla',
    created_at: '2015-10-02T03:22:00',
    updated_at: '2015-10-03T11:23:21',
    ...
  },
  {
    id: Y,
    ...
  },
  ...
]
[GET] /api/campaign/:id
Recovers a single campaign, where :id is an existing campaign identifier.

Success response:

Code	Meaning	Content
200	Success	Requested campaign body: {id: X, name: Y, ...}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaign/:id' \
       -H 'Authorization: <token>'

{
  id: X,
  name: 'Bla bla bla',
  created_at: '2015-10-02T03:22:00',
  updated_at: '2015-10-03T11:23:21',
  schedule: {...},
  targeting: {...},
  deals_and_pricing: {...},
  ...
}
NOTE: See Campaign Body section for a full description of all campaign attributes.

[POST] V2/api/campaign
Creates a new campaign. This method accepts both a full campaign body or a plain basic campaign attributes objects. For full campaign attributes description see Campaign Body section. The following description and example is designed for the simple way (plain one) of building campaigns.

Body params:

Field	Scope	Type	Description	Example
name	required	string	A name for humans	{..., name: 'Hello, world', ...}
type	required	string	Type of campaign	{..., type: 'smart-tv', ...}
advertiser	required	string	The event_id of the campaign	{..., advertiser: "mediasmart-xxt70yvxx1qfgglzxduqx7idqeo571we", ...}
countries	required	string	Some countries to run the campaign inside	{..., countries: ["SPA", "FRA"], ...}
description	optional	string	A description	{..., description: 'Bla bla bla', ...}
state	optional	string	The campaign state: active or inactive	{..., state: "active", ...}
deals_and_pricing	optional	object	Deals and pricing	{..., deals_and_pricing: { cpm: 10, cpa: 2, ... }, ...}
creatives	optional	array	List of existing creative identifiers to be attached to your campaign	`{…, creatives: [““, ““, …],
schedule	optional	object	Schedule campaign	{..., schedule: { budget_limit_publisher: 10, ... }, ...}
opportunity_window	optional	string	Only available for Connected TV campaigns with cross device	{..., opportunity_window: 'thirty_seconds, ...}
Available states are defined in the dictionary. They are self-descriptive:

active
inactive
deleted
preview
Available campaign types are defined in the dictionary as campaign_wizard_type

generic
dooh
smart-tv
synchronized
Available countries are defined in the geography dictionary:

ESP
FRA
CUB
EGY
…
Success response:

Code	Meaning	Content
201	Success	The created campaign: {id: X, name: Y, description: Z,...}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaign' \
       -H 'Authorization: <token>' \
       -X POST \
       -H 'Content-type: application/json' \
       --data '{"name": "My campaign", "description": "My campaign", \
                "kpi": "cpa", "value": 3.5, "iab_categories": ["IAB1-2", "IAB3"], \
                "advertiser_domain": "pepe.com", "countries": ["ESP", "FRA"]}'

{
  id: '...',
  name: 'My campaign',
  created_at: '2015-10-02T03:22:00',
  updated_at: '2015-10-03T11:23:21',
  ...
  deals_and_pricing: {
    cpm: 10,
    ...
  }
}
[PUT] V2/api/campaign/:id
Updates (partially) an existing campaign, where :id is a valid campaign identifier.

Body params: See Campaign Body section for a full description of all campaign attributes. Additional parameters are described below.

Field	Scope	Type	Description	Example
extend_state	optional	boolean	Force all strategies to get the same state we’re setting in the parent	{..., extend_state: true, ...}
Success response:

Code	Meaning	Content
200	Success	The updated campaign: {id: X, name: Y, description: Z,...}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaign/:id' \
       -H 'Authorization: <token>' \
       -X PUT \
       -H 'Content-type: application/json' \
       --data '{description": "New description", "targeting": {"identifiers": {"android": true, "ios": false}}}'

{
  id: X,
  name: 'Hello, World',
  description: 'New description',
  created_at: '2015-10-02T03:22:00',
  updated_at: '2015-10-03T11:23:21',
  ...
}
[GET] V2/api/campaign/:id/creatives
Retrieves the list of all campaign creatives in a campaign. A “Campaign creative” is a model that links a creative to a campaign.

Success response:

Code	Meaning	Content
200	Success	An array of campaign creatives: [{...}, {...}, ...]
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaign/:id/creatives' \
       -H 'Authorization: <token>' \
       -X GET

[
  {
    id: "<identifier>",
    state: "<active|inactive>",
    campaign: "<campaign_identifier>",
    creative: {...},
    ...
  },
  ...
]
NOTE: In the attribute creative of every campaign creative item in the retrieved array, you’ll find the whole creative body, the same as you can retrieve with [GET] /api/creative/:id

[GET] v2/api/campaign/:id/creatives/available
Retrieves a summary of all available creatives to be used from a specific campaign, where :id is a valid campaign identifier.

Success response:

Code	Meaning	Content
200	Success	An array of creative summaries: [{...}, {...}, ...]
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaign/:id/creatives/available' \
       -H 'Authorization: <token>' \
       -X GET

[
  {
    id: "<identifier>",
    type: "<image|tag|...>",
    name: "<creative_name>",
    thumbnail_url: "<url>",
    width: "<number>",
    height: "<number>",
    ...
  },
  ...
]
[POST] v2/api/campaign/:id/creative
Links a creative to a campaign, creating a CampaignCreative instance, where :id is an existing campaign identifier.

Request body:

Field	Scope	Type	Description	Example
creative_id	required	string	A creative identifier	{creative_id: "..."}
Success response:

Code	Meaning	Content
201	Success	The created campaign creative: {id: "...", creative: "...", ...}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaign/:id/creative' \
       -H 'Authorization: <token>' \
       -X POST \
       -H 'Content-type: application/json' \
       -d '{"creative_id": "<an_identifier>"}'

{
  id: "<identifier>",
  state: "<active|inactive>",
  campaign: "<campaign_identifier>",
  creative: {...},
  ...
},
[GET] v2/api/campaign/:id/creative/:cid
Retrieves a single campaign creative, including the full referenced creative document.

:id is a campaign identifier
:cid is a campaign creative identifier
Success response:

Code	Meaning	Content
200	Success	The campaign creative body: {id: X, name: Y, creative: Z, ...}
Error response

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call:

{
  "name": "...",
  "type": "...",
  "thumbnail_url": "...",
  "creative": {
    "id": "...",
    "click_url": "...",
    ...
  },
  ...
}
[PUT] v2/api/campaign/:id/creative/:cid
Updates a campaign creative document.

:id is a campaign identifier
:cid is a campaign creative identifier
Body params:

Field	Scope	Type	Description	Example
state	optional	string	Creative state	{..., state: 'active', ...}
keywords	optional	array	Segmentation keywords	{..., keywords: ["a", "b", ...], ...}
click_url	optional	string	Click URL to override creative one	{..., click_url: "http://blablabla.com", ...}
impression_urls	optional	array	Impression pixels, to override creative one	{..., impression_urls: ["http://a.com...", "http://b.com..."] ...}
Available states are defined in the dictionary, as campaign_creative_states:

inactive
active
Success response:

Code	Meaning	Content
200	Success	The updated campaign creative {id: X, name: Y, ...}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
400	Wrong request.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaign/:id/creative/:cid'
       -X PUT --data '{"keywords": ["a", "b"]}'
       -H 'Content-type: application/json'
       -H 'Authorization: <token>'

{
  id: ...,
  state: ...,
  keywords: ['a', 'b'],
  ...
}
[DELETE] v2/api/campaign/:id/creative/:cid
Unlinks a creative from a campaign, removing a CampaignCreative instance. :id is an existing campaign identifier, and :cid is a campaign creative identifier inside the campaign (not the creative identifier).

Success response:

Code	Meaning	Content
200	Success	The removed campaign creative: {...}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaign/:id/creative/:cid' \
       -H 'Authorization: <token>' \
       -X DELETE

{
  id: "<identifier>",
  state: "<active|inactive>",
  campaign: "<campaign_identifier>",
  creative: {...},
  ...
},
[GET] /api/campaign/:id/history
Retrieves the history of a campaign. Any changes you make in a campaign, will appear here.

:id is a campaign identifier
Success response:

Code	Meaning	Content
200	Success	The history campaign body
204	Success empty	The history campign is empty
Error response

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaign/:id/history' \
       -H 'Authorization: <token>'

{
  changes: [...],
  created_at: '2015-10-02T03:22:00',
  user: {...},
  ...
}
[POST] /api/campaign/:id/duplication
To be completed

Campaign body
This section describes the Campaign model and all its sections and attributes. A campaign is a set of first level attributes and some groups with second-level ones inside:

{
  first_level_attribute_1: ...,
  first_level_attribute_2: ...,
  ...
  section_A: {
    second_level_attribute_1: ...,
    second_level_attribute_2: ...,
  },
  section_B: {...},
  ...
}
First level attributes:

Field	Type	Description	Example
accept_googleadx_fee	boolean	Additional Ad serving costs	{..., accept_googleadx_fee: false, ...}
attribution_window_on_click	number	Number of days to attribute clicks	{..., attribution_window_on_click: 2, ...}
attribution_window_on_impression	number	Number of days to attribute impressions	{..., attribution_window_on_impression: 2, ...}
bundle	string	The app’s unique identifier	{..., bundle: "com.example.testapp", ...}
client_pricing	object (defined below)	Revenue you expect from your client	{..., client_pricing: {}, ...}
color	string	An hexadecimal color	{..., color: "#4CAF50", ...}
conversion_names	object (defined below)	Events 2-5	
conversion_one_is_required	boolean	Events 2-5 discarded unless event 1	{..., conversion_one_is_required: true, ...}
cost_percentage	number	A distribution value for parent+strategies	{..., cost_percentage: 34, ...}
count_reengagement_events	boolean	Count reengagement events	{..., count_reengagement_events: true, ...}
creatives	object (defined below)	Creatives-related attributes	{..., creatives: {}, ...}
cross_device	boolean	Accept to sync your Smart TV ads with ads in other devices in the same household {..., cross_device: true, ...}
deals_and_pricing	object (defined below)	Deals and pricing attributes	
description	string	The campaign description	{..., description: "I am a description", ...}
empowered_by_liveramp	boolean	The campaign has empowered by liveramp and shall use RampIDs for frequency capping and cross-screen targeting	{..., empowered_by_liveramp: true, ...}
empowered_by_liveramp_tos	boolean	Accept liveramp terms and conditions	{..., empowered_by_liveramp_tos: true, ...}
event_id	string	An existing tracking event name	{..., event_id: "hello", ...}
exported_at	string	ISO date of exportation	{..., exported_at: "2016-04-05T22:00.123Z", ...}
ghost_placebo	boolean	Use Ghost Ads	{..., ghost_placebo: true, ...}
id	string	The campaign identifier	{..., id: "jskfji2fj3f223", ...}
last_enabled_at	string	ISO date of last enabled	{..., last_enabled_at: "2016-04-05T22:00.123Z", ...}
measure_viewability	boolean	Accept Mediasmart terms and conditions	{..., measure_viewability: false, ...}
name	string	The campaign name	{..., name: "Hello world", ...}
opportunity_window	string	A period after a TV impact you would like to impact other devices in the same household	{..., opportunity_window: "twelve_hours", ...}
organization	object	Organization of the campaign	{..., organization: {...}, ...}
parent	object	Parent campaign	{..., parent: {...}, ...}
placebo_hold_days	number	Placebo hold days	{..., placebo_hold_days: 30 , ...}
placebo_percentage	number	Placebo percentage	{..., placebo_percentage: 100, ...}
retargeting	object (defined below)	Retargeting attributes	{..., retargeting: {}, ...}
schedule	object (defined below)	Scheduling attributes	{..., schedule: {}, ...}
state	string	The campaign state	{..., state: "inative", ...}
strategies	array of object	Strategy summaries list. These are created using a different route, please refer to campaign strategies	{..., strategies: [...], ...}
supports_many_conversions_one	boolean	Accept more than one event 1	{..., supports_many_conversions_one: true, ...}
supports_many_conversions_other	boolean	Accept more than one event 2-5	{..., supports_many_conversions_other: true, ...}
tags	array of string	Labels for searching purpose	{..., tags: ["video", "march"], ...}
targeting	object (defined below)	Targeting attributes	
tracking_tool	string	A tracking tool to use	{..., tracking_tool: "mediasmart", ...}
type	string	Type of campaign	{..., type: "proximity", ...}
users	array	List of users	{..., users: [{user1}, {user2}, ...], ...}
viewability_tracking_tool	string	A viewability tracking tool to use	{..., viewability_tracking_tool: "mediasmart viewability", ...}
created_at	string	ISO date of creation	{..., created_at: "2016-04-05T22:00.123Z", ...}
updated_at	string	ISO date of last update	{..., updated_at: "2016-04-05T22:00.123Z", ...}
Available states are defined as campaign_states in the dictionary:

active
inactive
deleted
preview
imported
Available campaign types are defined in the dictionary as campaign_wizard_type

generic
dooh
smart-tv
synchronized
Available tracking tools are defined as tracking_tools in the dictionary:

mediasmart
mediasmart_footfall
adsquare_footfall
adjust
appsflyer
branch
hasoffers
kochava
tune
s2s
SKAdNetwork
Available opportunity window options are defined as opportunity_window in the dictionary:

thirty_seconds
five_minutes
one_hour
twelve_hours
one_day
Second level attributes:

“client_pricing” section
Field	Type	Description	Example
model	string	Pricing Model	{..., model: "cpm", ...}
value	number	Pricing Value	{..., value: 1, ...}
Available values for client_pricing model:

cpm
cpa
cpc
“schedule” section
Field	Type	Description	Example
add_other_costs_to_limits	boolean	Consider other costs in budget	{..., add_other_costs_to_limits: false, ...}
budget_limit_publisher	number	Max publisher budget (%)	{..., budget_limit_publisher: 50, ...}
daily_limits_type	string	Pacing	{..., daily_limits_type: "auto", ...}
delivered_cost	number	Delivered cost	{..., delivered_cost: 0, ...}
finished_at	string	When the campaign should start	{..., finished_at: "2025-05-10", ...}
max_daily_clicks	number	Max clicks for every day	{..., max_daily_clicks: 500, ...}
max_daily_cost	number	Max cost for every day.	{..., max_daily_cost: 1000, ...}
max_daily_impressions	number	Max impressions for every day.	{..., max_daily_impressions: 10000, ...}
max_global_clicks	number	Max clicks for the whole campaign life.	{..., max_global_clicks: 1500, ...}
max_global_cost	number	Max cost for the whole campaign life.	{..., max_global_cost: 2500, ...}
max_global_impressions	number	Max impressions for the whole campaign life.	{..., max_global_impressions: 470000, ...}
max_impressions_user	number	Amount of impressions for the same user	{..., max_impressions_user: 50, ...}
max_impressions_user_day	number	Amount of impressions for the same user in a day	{..., max_impressions_user_day: 50, ...}
max_impressions_user_hour	number	Amount of impressions for the same user in a hour	{..., max_impressions_user_hour: 50, ...}
max_adviewed_user	number	Amount of adviewed events for the same user	{..., max_adviewed_user: 50, ...}
max_adviewed_user_day	number	Amount of impressions for the same user in a day	{..., max_adviewed_user_day: 50, ...}
max_adviewed_user_hour	number	Amount of impressions for the same user in a hour	{..., max_adviewed_user_hour: 50, ...}
one_click_per_user	boolean	No more ads should be shown to a user that has clicked	{..., one_click_per_user: true, ...}
started_at	string	When the campaign should start	{..., started_at: "2025-05-10", ...}
timezone	string	Time ranges when the campaign should run	{..., timezone: "2025-05-22 16:55", ...}
timing	array (defined below)	Time ranges when the campaign should run	{..., timing: [...], ...}
uniform_distribution	boolean	Distribute the campaign during the day	{..., uniform_distribution: true, ...}
Available values for schedule daily_limits_type:

auto (Pace uniformly during the campaign life)
manual (Set manual daily limits)
Every item in “timing” array is an object with the following attributes:

Field	Type	Description	Example
started_time_at	string	Start hour of this range	{..., started_time_at: "03:00", ...}
finished_time_at	string	End time of this range	{..., finished_time_at: "17:30", ...}
monday	boolean	If this range should run on monday	{..., monday: true, ...}
tuesday	boolean	If this range should run on tuesday	{..., tuesday: true, ...}
wednesday	boolean	If this range should run on wednesday	{..., wednesday: true, ...}
thursday	boolean	If this range should run on thursday	{..., thursday: true, ...}
friday	boolean	If this range should run on friday	{..., friday: true, ...}
saturday	boolean	If this range should run on saturday	{..., saturday: true, ...}
sunday	boolean	If this range should run on sunday	{..., sunday: true, ...}
Example:

{
  ...
  schedule: {
    started_at: '2016-05-21',
    finished_at: '2016-05-25',
    max_global_cost: 5400,
    max_daily_cost: 1000,
    max_daily_impressions: 43000
    uniform_distribution: true,
    one_click_per_user: false,
    timing: [{
      monday: true,
      tuesday: true,
      wednesday: true,
      thursday: true,
      friday: true,
      saturday: false,
      sunday: false,
      started_time_at: "17:00",
      finished_time_at: "23:00",
    }, {
      monday: false,
      tuesday: false,
      wednesday: false,
      thursday: false,
      friday: false,
      saturday: true,
      sunday: true,
      started_time_at: "09:00",
      finished_time_at: "23:00",
    }]
  },
  ...
}
“targeting” section
Field	Type	Description	Example
age	object or null	Age ranges allowed. Available ranges are defined in the main dictionary as age. Extra value blacklist supported.	{..., age: {'lt13': true, 'gt13-lt17': true, blacklist: true}, ...}
min_app_rating	number	Minimum App Store Rating your campagin will appear in. From 1 to 5	{..., "min_app_rating": 3, ...}
auction_type	object	Auction type [first_price, second_price]	{..., auction_type: {"first_price"}, ...}
audience_mapping_value	boolean	Set audience mapping for a specific campaign	{..., audience_mapping_value: false, ...}
categories	array	List of publisher categories. Available ones are defined in the main dictionary as publisher_categories	{..., categories: ['adult', 'automobile', 'games', 'games:action'], ...}
cities	array	List of cities (see dictionary)	{..., cities: ['1234321', '144221', '38892'], ...}
connection	object or null	Type of connections where the campaign should run. Available ones are defined in the main dictionary as connection_type. Special value blacklist can be included.	{..., connection: {'cellular_3g': true, 'cellular_4g': true, wifi: false, blacklist: false}, ...}
countries	array	List of country codes (see dictionary)	{..., countries: ['ESP', 'FRA'], ...}
device_makers	array	List of devices makers (manufacturers). Available ones can be extracted performing a real time drilldown using the variable p:make	{..., device_makers: ["apple", "nokia"], ...}
device_models	array	List of devices models. Available ones can be extracted performing real time drilldown using the variable p:model . Special value blacklist can be included.	{..., device_models: ["iphone_5s", "samsung_s6"], ...}
device_type	object or null	Type of devices where the campaign should run. Available ones are defined in the main dictionary as device_type. Special value blacklist can be included.	…
distribute_among_areas	boolean	Distribute among areas	{..., distribute_among_areas: true, ...}
dmp_audiences	array	DMP audiences or organization’s audiences that the campaign is targeted to. An user has to be part of at least one of the audiences in this section in order to bid for it.	{..., dmp_audiences: ['audA', 'audB', 'audC'], ...}
dmp_audiences_and	array	DMP audiences or organization’s audiences that the campaign is targeted to. An user has to be part of all the audiences in this section in order to bid for it.	{..., dmp_audiences_and: ['audA', 'audB', 'audC'], ...}
dmp_audiences_not	array	DMP audiences or organization’s audiences that the campaign is targeted to. An user can not be part of any of the audiences in this section in order to bid for it.	{..., dmp_audiences_not: ['audA', 'audB', 'audC'], ...}
exchanges	object or null	Ad Exchanges where the campaign should run. Available AdExchanges are defined in the main dictionary as exchanges	{..., exchanges: {mopub: true, rubicon: false, ...}, ...}
exclude_dnt	boolean	Exclude DNT inventory	{..., exclude_dnt: true, ...}
gender	object or null	Gender allowed (male or female). Extra value blacklist supported.	{..., gender: {male: true, female: false, blacklist: false}, ...}
geolist_acquisition	string	Geolist identifier for targeting	{..., geolist_acquisition: "<id>", ...}
geolist_classification	string	Geolist identifier for reporting	{..., geolist_classification: "<id>", ...}
geolist_conversion	string	Geolist identifier for conversion	{..., geolist_conversion: "<id>", ...}
geolocation_areas	object (defined below)	Geolocation areas	{..., geolocation_areas: {}, ...}
identifiers	object or null (defined below)	Identifier types allowed for the campaign	{..., identifiers: {ifa: true, gaid: false, web: true}, ...}
ignore_global_blacklists	boolean	Ignore global blacklist	{..., ignore_global_blacklists: true, ...}
interests	array	List of user interest about categories. Available ones are defined in the main dictionary as publisher_categories	{..., interests: ['automobile'], ...}
isps	array	Internet Service Provider	{..., isps: ['vodafone', 'orange'], ...}
languages	array	List of user languages. Available ones are defined in the main dictionary as languages	{..., languages: ['es', 'en'], ...}
lotame_audiences	array	List of Lotame audiences. Available ones are defined in the main dictionary as lotame_audiences	{..., lotame_audiences: ['68958', '68959'], ...}
mandatory_ads_txt	boolean	Only inventory with Ads.txt	{..., mandatory_ads_txt: true, ...}
mandatory_bundle	boolean	Only inventory with Bundle ID	{..., mandatory_bundle: true, ...}
mandatory_domain	boolean	Only inventory with domain	{..., mandatory_bundle: true, ...}
mandatory_tagid	boolean	Only inventory with Tag ID	{..., mandatory_tagid: true, ...}
manual_keywords_and	array	List of keywords where all of them have to be present	{..., manual_keywords_and: ['key3', 'key4', 'key5'], ...}
manual_keywords_not	array	List of keywords where none can be present	{..., manual_keywords_not: ['key6'], ...}
manual_keywords_or	array	List of keywords where at least one has to be present	{..., manual_keywords_or: ['key1', 'key2'], ...}
manual_keywords_rule	array of arrays of string	A custom keywords logic: AND of ORs	{..., manual_keywords_rule: [["p:a:one", "p:b:two"], ["p:c:three"], ...], ...}
measurement	string	Target only traffic whose viewability is measurable. Available ones are defined in the main dictionary as measurement	{..., measurement: 'ias', ...}
mosaic	array	List of mosaic profiles (see dictionary)	{..., mosaic: ['esp:02:bla'], ...}
operators	array	List of operators. Available ones are defined in the main dictionary as operators	{..., operators: ['vodafone', 'jazztel', 'movistar'], ...}
os	object or null	Operating systems where the campaign should run. Available ones are defined in the main dictionary as operating_systems	{..., os: {android: true, blackberry: false}, ...}
pages	array	List of publishers domains or urls to match	{..., pages: ['angrybirds.com', 'example.com'], ...}
pretargeting_policy	string	Pretargeting policy	{..., pretargeting_policy: 'off', ...}
publisher_type	object or null	Types of publisher allowed for the campaign. Available ones are defined in the main dictionary as publisher_type	`{…, publisher_type: {app: true, web: false}, …}``
publishers	array	List of publisher listsgit you want to target. Publisher lists should be used, using “list:” prefix	{...,[ 'list1:<id1>', 'list2:<id2>', ], ...}
blacklist_publishers	array	List of publisher listsgit you want to block. Blocked publisher lists should be used, using “list:” prefix	{...,[ 'list1:<id1>', 'list2:<id2>', ], ...}
publishers_rules	array	List of publishers with their specific prices for microbidding.	{..., publishers_rules: [{price: '1.2', formula: ['key3']}, {price: '0.54', formula: ['key1', 'key2']}], ...}
regions	array	List of regions (see dictionary)	{..., regions: ['ESP:CL', 'ESP:EX'], ...}
rewarded	boolean	Target only rewarded videos	{..., rewarded: false, ...}
sim_countries	array	List of SIM countries	{..., rewarded: false, ...}
target_skadnetwork_only	boolean	Only inventory compatible with SKAdNetwork	{..., target_skadnetwork_only: false, ...}
universal_ids	object or null (defined below)	Universal Ids allowed for the campaign	{..., universal_ids: {mediasmart_id: true}, ...}
use_categories_as_blacklist	boolean	Use categories as blacklist instead of whitelist.	{..., use_categories_as_blacklist: true, ...}
use_device_makers_as_blacklist	boolean	Use device makers as blacklist instead of whitelist	{..., use_device_makers_as_blacklist: true, ...}
use_device_models_as_blacklist	boolean	Use device models as blacklist instead of whitelist	{..., use_device_models_as_blacklist: true, ...}
use_geolist_conversion_as_targeting_blacklist	boolean	Do not buy traffic inside the conversion geolist	{..., use_geolist_conversion_as_targeting_blacklist: true, ...}
use_isps_as_blacklist	boolean	Use ISPs as blacklist	{..., use_isps_as_blacklist: false, ...}
use_languages_as_blacklist	boolean	Use languages as blacklist instead of whitelist	{..., use_languages_as_blacklist: true, ...}
use_mosaic_as_blacklist	boolean	Use mosaic profiles as blacklist instead of whitelist	{..., use_mosaic_as_blacklist: true, ...}
use_operators_as_blacklist	boolean	Use operators as blacklist instead of whitelist	{..., use_operators_as_blacklist: true, ...}
use_pages_as_blacklist	boolean	Use publishers domain or urls as blacklist instead of whitelist	{..., use_pages_as_blacklist: true, ...}
use_publishers_as_blacklist	boolean	Use publishers list as blacklist instead of whitelist	{..., use_publishers_as_blacklist: true, ...}
use_sim_countries_as_blacklist	boolean	Use SIM countries as blacklist	{..., use_sim_countries_as_blacklist: true, ...}
use_targeting_users_list_for_pretargeting	boolean	Use dmp_audiences_and, dmp_audiences and dmp_audiences_not fields to reach for similar users	{..., use_targeting_users_list_for_pretargeting: true, ...}
use_user_agents_as_blacklist	boolean	Use user agents as blacklist instead of whitelist	{..., use_user_agents_as_blacklist: true, ...}
user_agents	array	List of user agent patterns to match	{..., user_agents: ["pattern1", "pattern2"], ...}
video_positions	object	Video positions	{..., video_positions: {}, ...}
will_not_copy_audiences	boolean	A confirmation not copy external audiences. Required when an external audience is used	{..., will_not_copy_audiences: true, ...}
zipcodes	array	List of zip codes	{..., zipcodes: ['16003', '24005', '28012'], ...}
NOTE: Audience IDs of third party providers, like adsquare, must include the provider as a prefix. For instance, if you want to target audiences 1234 and 5678 from Adsquare (retrieved with [GET] /api/audiences) you’ll need to use adsquare-1234 and adsquare-5678 as identifiers from the targeting fields, like dmp_audiences_and.

You can choose the minimum rating of the apps your campaign will appear in. For instance: "min_app_rating": 3

Available values for targeting identifiers are defined as identifiers in the main dictionary:.

ifa
gaid
fake
web
Available values for targeting universal ids are defined as universal_ids in the main dictionary:.

none
mediasmart_id
ramp_id
Available pretargeting policies are defined in the main dictionary as pretargeting_policy:

off
very-restrictive
normal
less-restrictive
geolocation_areas is a list of items with the following attributes:

Field	Type	Scope	Description	Example
latitude	number	required	Latitude in decimal degrees format	{..., latitude: 40.4060324, ...}
longitude	number	required	Longitude in decimal degrees format	{..., longitude: -3.7234421, ...}
radius	number	required	Radius of the area (in metres)	{..., radius: 1500, ...}
text	string	required	Text to show inside dynamic creatives shown in this area	{..., text: 'You are in Book Street', ...}
id	string	optional	An identifier for reporting	{..., id: 'my home', ...}
name	string	optional	A name for reporting	{..., name: 'where I live', ...}
Available values for targeting video_positions:

pre-roll
mid-roll
post-roll
Example:

{
  ...
  targeting: {
    exchanges: { mopub: true, appnexus: true, adiquity: true, openx: true },
    connection: null, // Any connection
    device_type: { phone: true, blacklist: true },
    user_agents: ['webkit'],
    use_user_agents_as_blacklist: false,
    os: null, // Any operating system
    countries: ['ESP', 'FRA'],
    operators: ['vodafone'],
    use_operators_as_blacklist: true,
    languages: ['es', 'en'],
    mosaic: [],
    age: { 'lt13': true, 'gt13-lt17': true, blacklist: true },
    gender: null,
    categories: ['adult'],
    use_categories_as_blacklist: true,
    publishers: ['p:pub:keyword:one', '*sport*'],
    ...
  },
  ...
}
“retargeting” section
Field	Type	Description	Example
keywords_to_add_on_click	array	Keywords to be added to target users, on click	{..., keywords_to_add_on_click: ['key1', 'key2'], ...}
keywords_to_add_on_conversion_1	array	Keywords to be added to target users, on conversion 1	{..., keywords_to_add_on_conversion_1: ['key3', 'key4', 'key5'], ...}
retargeting_policy	string	Retargeting policy (deprecated)	{..., retargeting_policy: 'off', ...}
targeting_users_list	string	Audience identifier (deprecated, please use: dmp_audiences in targeting section)	{..., targeting_users_list: 'jkj2302923ur0id2', ...}
use_targeting_users_list_as_blacklist	boolean	Use users list as blacklist instead of whitelist (deprecated, please use: dmp_audiences_not in targeting section)	{..., use_targeting_users_list_as_blacklist: true, ...}
users_list_on_click	string	Audience identifier	{..., users_list_on_click: '28982y3y2jj', ...}
users_list_on_impressions	string	Audience identifier	{..., users_list_on_impressions: 'uhiu23y2iuh32i', ...}
users_list_on_adviewed	string	Audience identifier	{..., users_list_on_adviewed: 'ksjdu7ke9sjli3g', ...}
users_lists_on_events	object (defined below)	Audiences to be build on events	{..., users_lists_on_events: {}, ...}
users_lists_on_video	object (defined below)	Audiences to be build on video events	{..., users_lists_on_video: {}, ...}
users_lists_on_events is an object with the following fields:

Field	Type	Description	Example
on_event_1	string	Audience identifier	{..., on_event_1: "rk67wqcmjoucrlbc1jtbb0k42", ...}
on_event_2	string	Audience identifier	{..., on_event_2: "uk1zif52rnmv05kk09ztpbkgw", ...}
on_event_3	string	Audience identifier	{..., on_event_3: "9wm5o2lru1yux8u6t6fxb8ebg", ...}
on_event_4	string	Audience identifier	{..., on_event_4: "hkl70ur0yxglrn7ajeimjyomj", ...}
on_event_5	string	Audience identifier	{..., on_event_5: "pbhu87gpi1pjmuirfwbhqnkoq", ...}
Defining a list of audiences to build on every event.

users_lists_on_video is an object with the following fields:

Field	Type	Description	Example
on_video_start	string	Audience identifier	{..., on_video_start: "m4uyv98hukevnfwiu1ubmqmea", ...}
on_video_first_quartile	string	Audience identifier	{..., on_video_first_quartile: "3cxg69rwkhamhbasemrj4tpsy", ...}
on_video_second_quartile	string	Audience identifier	{..., on_video_second_quartile: "117rvu6bkd0x0pysed49zx2fx", ...}
on_video_midpoint	string	Audience identifier	{..., on_video_midpoint: "37m0vow2zy0nkzrkiuxnay8g0", ...}
on_video_third_quartile	string	Audience identifier	{..., on_video_third_quartile: "qbywoqk5l73x7ka65u183irwq", ...}
on_video_complete	string	Audience identifier	{..., on_video_complete: "gm9jzvhwc84bwloyzkl3ivd30", ...}
Defining a list of audiences to build on every video event.

Available retargeting policies are defined in the main dictionary as retargeting_policy:

off
acquisition
retargeting
Please note this field is deprecated and should not be used anymore.

Example:

{
  ...
  retargeting: {
    users_list_on_impressions: 'uhiu23y2iuh32i'
    users_lists_on_events: {
      on_event_1 : 'rk67wqcmjoucrlbc1jtbb0k42',
      on_event_2 : 'uk1zif52rnmv05kk09ztpbkgw',
    },
    users_lists_on_video: {
      on_video_start : 'm4uyv98hukevnfwiu1ubmqmea',
      on_video_complete: 'gm9jzvhwc84bwloyzkl3ivd30',
    },
  },
  ...
}
“deals_and_pricing” section
Field	Type	Description	Example
cpa	number	Goal CPA	{..., cpa: 3.8, ...}
cpc	number	Goal CPC	{..., cpc: 0.15, ...}
cpm	number	Initial CPM	{..., cpm: 10, ...}
cpv	number	Goal CPV	{..., cpv: 10, ...}
cpv_event	string	Video event to use for optimization	{..., cpv_event: 'videocomplete', ...}
deal_policy	string	Deal policy	{..., deal_policy: 'plc', ...}
deals	array	List of deals to use	{..., deals: ['x123', 'y234', 'z345'], ...}
event_number_for_cpa	number	Event to use for CPA optimization	{..., event_number_for_cpa: 3, ...}
exchange_breakdown	boolean	Optimization per exchange instead of global	{..., exchange_breakdown: false, ...}
rules	array (defined below)	Pricing rules	{..., rules: [{rule1}, {rule2}, ...], ...}
Available deal policies are defined in the main dictionary as deal_policy:

off: Do not use deals
plc: Pure placement
per: Performance
Available video events are defined in the main dictionary as cpv_events:

videostart: ‘Video start’,
videofirstquartile: ‘Video 25% viewed’,
videomidpoint: ‘Video 50% viewed’,
videothirdquartile: ‘Video 75% viewed’,
videocomplete: ‘Video completed’,
rules is an array of objects defined as follows:

Field	Type	Description	Example
formula	array	List of keywords	{..., formula: ['key1', 'key2', 'key3'], ...}
price	number	Pricing factor to apply when formula is matched	{..., price: 1.5, ...}
Example:

{
  ...
  deals_and_pricing: {
    deal_policy: 'plc',
    deals: ['deal1', 'deal2', 'deal3'],
    cpm: 10,
    cpc: 0.1,
    exchange_breakdown: true,
    rules: [{
      formula: ['key1', 'key2'],
      price: 1.2
    }, {
      formula: ['key3'],
      price: 2,
    }],
  },
  ...
}
“creatives” section
Field	Type	Description	Example
campaign_creatives	array	List of campaign creative instances	{..., campaign_creatives: [{item1}, {item2}, ...}
Campaign creative can have their own impression_pixel and click_url that will overwrite the ones that are in the creative itself.

Example:

{
  ...
  creatives: {
    campaign_creatives: [{
      id: 'ou2iou2io3u',
      impression_pixel: `https://pixel.com',
      creative: {...}
    }, {
      id: '23j2hkj2h3',
      keywords: ['key3'],
      click_url: `mediasmart.io`
      creative: {...}
    }]
  },
  ...
}
Campaigns > Strategies
A strategy is a campaign, but linked to another campaign that is considered as a parent.

Inheritance
All attributes set to undefined inside a strategy are inherited from its parent campaign (but mandatory ones, like name, state or cost_percentage).

If an attribute inside a strategy has a value (i.e is not undefined) the attribute will not be inherited.

If an attribute inside a strategy is set to the same value as the parent campaign, then it will be replaced by undefined so inheritance will be enabled.

Strategies can be managed as common campaigns, in the sense that the following routes can be used:

[GET] /api/campaign/:id
[PUT] /api/campaign/:id
[GET] /api/campaign/:id/creatives
[GET] /api/campaign/:id/creatives/available
[POST] /api/campaign/:id/creative
[DELETE] /api/campaign/:id/creative/:cid
The following sections describe additional routes to work with strategies:

[GET] /api/campaign/:id/strategies
List all strategies linked to a parent campaign, where :id is an existing campaign identifier.

Success response:

Code	Meaning	Content
200	Success	An array of strategy summaries: [{...}, {...}, ...]
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaign/:id/strategies' \
       -H 'Authorization: <token>' \
       -X GET

[
  {
    parent_id: "<parent_campaign_identifier>", // Previously called "Control" campaign
    id: "<campaign_identifier>",
    name: "<strategy_name>", // Used as A/B tag
    color: "<hexadecimal_color>",
    ...
  },
  ...
]
NOTE: To retrieve a full strategy just use the common campaign route: [GET] /api/campaign/:id.

[POST] /api/campaign/:id/strategy
Creates a new strategy linked to a provided parent campaign, where :id is the campaign parent identifier. Takes in account that only first-level campaigns can be a parent, so another strategy cannot be used as parent campaign.

Request body:

Field	Scope	Type	Description	Example
name	required	string	A name for the strategy	{..., "name": "bla bla", ...}
state	required	string	A campaign state for the strategy	{..., "state": "active", ...}
cost_percentage	optional	number	A cost % for this strategy inside the campaign	{..., "cost_percentage": 0.4, ...}
Success response:

Code	Meaning	Content
201	Success	The created campaign (strategy): {id: "...", name: "...", ...}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call:

$ curl 'https://api.mediasmart.io/api/campaign/:id/strategy' \
       -H 'Authorization: <token>' \
       -X POST  \
       -H 'Content-type: application/json' \
       -d '{"name": "cosilla", "state": "active", "cost_percentage": 0.5}'

{
  id: "<campaign_identifier>",
  name: "<strategy_name>",
  parent: {...},
  schedule: {...},
  targeting: {...},
  deals_and_pricing: {...},
  ...
}
Creatives
These routes let you manage your organization’s creatives.

[GET] /api/creatives
Retrieves all available creatives summary.

URL params:

Field	Scope	Type	Description	Example
state	optional	string	Creative state	state=active
Available states are defined in the dictionary. They are self-descriptive:

active
archived
deleted
imported
pending-approval
rejected
Success response:

Code	Meaning	Content
200	Success	A list of creative summaries: [{...}, {...}, ...]
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call:

$ curl 'https://api.mediasmart.io/api/creatives' \
       -H 'Authorization: <token>'

[
   {
      "id" : "<identifier>",
      "type" : "<creative_type>",
      "state" : "pending-approval",
      "name" : "<creative_name>",
      "description" : "<creative_description>"
      "width" : <width_in_pixels>,
      "height" : <height_in_pixels>,
      "thumbnail_url" : "<image_url>",
      "tags" : ["label1", "label2", ...],
      "created_at" : "<iso_date>",
      "updated_at" : "<iso_date>",
  },
  ...
]
[GET] /api/creative/:id
Retrieves a single creative, where :id is a creative identifier.

Success response:

Code	Meaning	Content
200	Success	The required creative {id: X, name: Y, ...}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
404	Not found
403	Forbidden action.
Sample call:

$ curl 'https://api.mediasmart.io/api/creative/<an_identifier>'
       -H 'Authorization: <token>'

{
  id: "<identifier>",
  name: "<the_name>",
  description: "<description>",
  ...
}
[POST] /api/creative (multipart)
Adds a new creative in your organization

Body params:

Field	Scope	Type	Description	Example
type	required	string	Creative type	{..., type: 'image', ...}
state	optional	string	Creative state	{..., state: 'active', ...}
name	required	string	A name for humans	{..., name: 'Hello, world', ...}
description	optional	string	A description	{..., description: 'Bla bla bla', ...}
tags	optional	string	A JSON array of string labels	{..., tags: '["one", "two", ...]', ...}
attributes	required	string	A JSON array of numbers	{..., attributes: '[1, 6, ...]', ...}
impression_urls	optional	array	A JSON array of URLs	{..., impression_urls: '["http://a.com", "http://b.com", ...]', ...}
impression_html	optional	string	An HTML impression pixel	{..., impression_html: '<...>', ...}
Available states are defined in the dictionary:

active
archived
deleted
imported
pending-approval
rejected
Available types are defined in the dictionary:

image: common banner
video: custom video
audio: custom audio
external-video: external VAST
native: native ad
dynamic: images with dynamic content
tag: third party HTML+JS and MRAID tags
Available attributes are defined in the dictionary:

1: Audio autoplay
2: Audio user initiated
3: Expandable (auto)
4: Expandable (user initiated / click)
5: Expandable (user initiated / rollover)
6: In-banner video (autoplay)
7: In-banner video (user initiated)
8: Pop-up (over, under, exit)
9: Provocative or suggestive
10: Shaky, flashing, extreme animations
11: Surveys
12: Text only
13: Embedded game
14: Window dialog/alert
15: Has audio on/off control
16: Ad can be skipped
In addition to the generic fields, each creative type should include its own attributes on creation:

Image banners:

Field	Scope	Type	Description
file	required	File	One or more attached image files (multipart). A new creative will be created for each file.
Video ads:

Field	Scope	Type	Description
file	required	File	An attached video file (multipart). Some SSPs support landscape and portrait videos, so you can upload two video files with complementary aspect ratios.
video_completion_url:	optional	String	Client pixel triggered when the video completes
video_error_url:	optional	String	Client pixel triggered when the video has an error.
video_first_quartile_url:	optional	String	Client pixel triggered when the video reaches 25%.
video_midpoint_url:	optional	String	Client pixel triggered when the video reaches 50%.
video_skip_url:	optional	String	Client pixel triggered when the user skips the video.
video_start_url:	optional	String	Client pixel triggered when the video starts
video_third_quartile_url:	optional	String	Client pixel triggered when the video reaches 75%.
companion.url	optional	String	The click URL for an optional companion/endcard ad. Required if there is a companion.
companion.width	optional	String	Width of the companion ad. Required if there is a companion.
companion.height	optional	String	Height of the a companion ad. Required if there is a companion
companion.banner	optional	String	URL where the companion image is located, in case this is an static image companion.
companion.html	optional	String	HTML code of the richmedia companion. Either a banner or an html code must be submited in companions.
Audio ads:

Field	Scope	Type	Description
file	required	File	An attached audio file (multipart).
companion.url	optional	String	The click URL for an optional companion/endcard ad. Required if there is a companion.
companion.width	optional	String	Width of the companion ad. Required if there is a companion.
companion.height	optional	String	Height of the a companion ad. Required if there is a companion
companion.banner	optional	String	URL where the companion image is located, in case this is an static image companion.
companion.html	optional	String	HTML code of the richmedia companion. Either a banner or an html code must be submited in companions.
External video:

Field	Scope	Type	Description
vast_wrapper.url	required	String	A valid VAST location URL
vast_wrapper.duration	required	Number	The duration of the referenced video
vast_wrapper.xml	optional	String	XML VAST Tag of the external video. If this is sent, the url attribute is ignored.
Native ads:

Field	Scope	Type	Description	Example
native_settings.title	required	String	Ad title	native_settings.title="Hello, world"
native_settings.text	required	String	Ad text	native_settings.text="I am a text"
native_settings.action	required	String	Action text	native_settings.action="Sign up"
native_settings.rating	optional	Number	The app store rating 0-5	native_settings.rating="3"
native_settings.icon300x300	required	File	An attached image file for the icon	
native_settings.image1200x627	optional	File	An attached image file for 1200x627	
native_settings.image580x480	optional	File	An attached image file for 580x480	
native_settings.image640x480	optional	File	An attached image file for 640x480	
native_settings.image356x200	optional	File	An attached image file for 356x200	
native_settings.image240x200	optional	File	An attached image file for 240x200	
native_settings.image180x60	optional	File	An attached image file for 180x60	
native_settings.image138x115	optional	File	An attached image file for 138x115	
native_settings.image90x75	optional	File	An attached image file for 90x75	
native_settings.image72x60	optional	File	An attached image file for 72x60	
file	optional	File	An attached video file	
Tags (HTML+JS and MRAID):

Field	Scope	Type	Description	Example
html	required	String	HTML markup, maybe including JS scripts, images, etc.	html="<img src='...'/><script src..."
is_mraid	required	Boolean	Should be marked if mraid library is used	is_mraid=true
is_secure	required	Boolean	The tag only uses HTTPS and follows Apple iOS 9 guidelines. See: https://goo.gl/UglmM8	is_secure=true
is_responsive	optional	Boolean	The code of the tag is responsive and adapt automatically to the sizes defined in the field responsive_sizes	is_responsive=true
responsive_sizes	optional	array	The sizes that this tag allows in case it is responsive. This field is mandatory if is_responsive=true. The available sizes can be consulted in the dictionary	{..., responsive_sizes: ["320x50", "320x480", ...], ...}
thumbnail_url	required	File	Image file to be used as thumbnail	
Dynamic ads:

Field	Scope	Type	Description	Example
dynamic_settings.top	required	Number	Top margin for the text box (in px)	dynamic_settings.top=20
dynamic_settings.bottom	required	Number	Bottom margin for the text box (in px)	dynamic_settings.bottom=20
dynamic_settings.left	required	Number	Left margin for the text box (in px)	dynamic_settings.left=20
dynamic_settings.right	required	Number	Right margin for the text box (in px)	dynamic_settings.right=20
dynamic_settings.font_size	optional	Number	Font size for the text (in px)	dynamic_settings.font_size=12
dynamic_settings.color	optional	String	Hexadecimal color for the text	dynamic_settings.color=#ff0033
Response and examples
Success response:

Code	Meaning	Content
201	Success	The new creative: {"id": "...", "name": "...", ...}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
400	Bad request.
Sample calls:

$ curl 'https://api.mediasmart.io/api/creative' \
       -H 'Authorization: <token>' \
       -X POST \
       -F type=image \
       -F name='Hello world' \
       -F file=@./my/banner.png

{
  id: "...",
  name: "Hello world",
  file: "<cdn_url>",
  thumbnail_url: "<cdn_url>",
  width: 320,
  height: 50,
  ...
}
$ curl 'https://api.mediasmart.io/api/creative' \
       -H 'Authorization: <token>' \
       -X POST \
       -F type=tag \
       -F name='Hello world' \
       -F html=' <div>hello, world</div>' # The space before "<" is for curl
       -F width=320
       -F height=240
       -F thumbnail_url=@./my/banner.png

{
  id: "...",
  type: "tag",
  name: "Hello world",
  thumbnail_url: "<cdn_url>",
  width: 320,
  height: 240,
  html: "<div>hello, world</div>",
  ...
}
$ curl 'https://api.mediasmart.io/api/creative' \
       -H 'Authorization: <token>' \
       -X POST \
       -F type=video \
       -F name='A video example' \
       -F file=@./my/video.wmv

{
  id: "...",
  name: "A video example",
  file: "<cdn_url>",
  thumbnail_url: "<cdn_url>",
  vast_settings: {
    duration: 23,
    mediafiles: [{
      "height": 320,
      "width": 480,
      "bitrate": 400,
      "mime": "video/mp4",
      "url": "<cdn_url>"
    }, ...]
  }
  ...
}
$ curl 'https://api.mediasmart.io/api/creative' \
       -H 'Authorization: <token>' \
       -X POST \
       -F type=audio \
       -F name='An audio example' \
       -F file=@./my/audio.m4a

{
  id: "...",
  name: "An audio example",
  file: "<cdn_url>",
  vast_settings: {
    duration: 12,
    mediafiles: [{
      "bitrate": 128,
      "mime": "audio/ogg",
      "url": "<cdn_url>"
    }, ...]
  }
  ...
}
$ curl 'https://api.mediasmart.io/api/creative' \
        -H 'Authorization: <token>' \
        -X POST \
        -F type=dynamic \
        -F name='Dynamic test ad' \
        -F file=@./my/banner.png \
        -F dynamic_settings.top=30 \
        -F dynamic_settings.bottom=120 \
        -F dynamic_settings.color=#443322

{
  id: "...",
  name: "Dynamic test ad",
  file: "<cdn_url>",
  thumbnail_url: "<cdn_url>",
  width: 320,
  height: 50,
  dynamic_settings: {
    top: 30,
    bottom: 120,
    left: 0,
    right: 0,
    color: '#443322'
  }
  ...
}
$ curl 'http://localhost:8989/api/creative' \
       -H 'Authorization: <token>' \
       -X POST \
       -F type=native
       -F name='Native test' \
       -F native_settings.title='My Ad' \
       -F native_settings.text='I am an ad' \
       -F native_settings.action='Click here' \
       -F native_settings.icon300x300=@./my/image_300x300.png \
       -F native_settings.image580x480=@./my/image_580x480.png

{
  "id": "...",
  "name": "Native test",
  "type": "native",
  "thumbnail_url": "<cdn_url>",
  "native_settings": {
     "title": "My Ad",
     "text": "I am an ad",
     "icon50x50": "<cdn_url>",
     "icon64x64": "<cdn_url>",
     "icon75x75": "<cdn_url>",
     "icon80x80": "<cdn_url>",
     "icon120x120": "<cdn_url>",
     "icon300x300": "<cdn_url>",
     "action": "Click here",
     "image1200x627": null,
     "image580x480": <cdn_url>,
     "image640x480": null,
     "image356x200": null,
     "image240x200": null,
     "image180x60": null,
     "image138x115": null,
     "image90x75": null,
     "image72x60": null,
     "rating": null,
     "video": {
         "duration": null,
         "mediafiles": []
     }
  },
  ...
}
NOTE: Keep in mind that some creative types creation could take some minutes (specially video ones), while our server converts files and computes thumbnails.

NOTE: For the moment, video ads can be created only in Production environment. while our server converts files and computes thumbnails.

[PUT] /api/creative/:id (multipart)
Perform updates over an existing creative. Where :id is the creative identifier.

This offers exactly the same interface than [POST] /api/creative/:id route, shown above.

Sample call:

$ curl 'https://api.mediasmart.io/api/creative/<identifier>'
       -H 'Authorization: <token>'
       -X PUT
       -F attributes='[1,2,3]'
       -F dynamic_settings.top=30

{
  "id": "...",
  ...
  "attributes" : [
    "1",
    "2",
    "3"
  ],
  "dynamic_settings" : {
    "top" : 30,
    ...
  },
  "type" : "native",
  ...
}
[DELETE] /api/creative/:id
Marks a creative as deleted. It is equivalent to update a creative changing its state to deleted.

Success response:

Code	Meaning	Content
200	Success	The deleted creative {id: X, name: Y, ...}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Creative not found
Sample call

$ curl 'https://api.mediasmart.io/api/creative/<an_identifier>' \
       -X DELETE
       -H 'Authorization: <token>'
Audiences
These routes let you manage your organization’s audiences.

[GET] /api/audiences
Retrieves all available audiences in your organization.

Query params:

Field	Scope	Type	Description
area	optional	string	Audiences provider (adsquare, mediasmart…)
Success response:

Code	Meaning	Content
200	Success	Plain object: {attr1: 'x', attr2: 'y', ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/audiences' \
       -H 'Authorization: <token>'

[
  {
     "id" : "<identifier>",
     "name" : "<audience_name>",
     "description" : "<audience_description>"
     "items" : <items_count>,
     "beacon": "<beacon_url>",
     "beacon_eu": "<beacon_url>",
     "allowed_organizations": [],
     "countries": <array_of_contries>,
     "favorite": "<favorite>",
     "isRecency": <boolean>m
     "items": <number>
     "state": "<audience_state>",
     "type": "<audience_type: Private, Time Based...>",
     "created_at" : "<iso_date>",
     "updated_at": "<iso_date>"
  },
  ...
]
[GET] /api/audience/:id
Recovers a single audience, where :id is an existing audience identifier.

Success response:

Code	Meaning	Content
200	Success	Requested audience body: {id: X, name: Y, ...}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call:

$ curl 'https://api.mediasmart.io/api/audience/:id' \
       -H 'Authorization: <token>'

{
  id: 'X',
  name: 'name',
  organization: 'Y',
  advertiser_name: 'Name',
  allowed_organizations: [],
  audience_insights: [],
  beacon: 'https://3ma79ae7cua.com...',
  beacon_eu: 'https://3ma79ae7cua.com...',
  campaigns: [],
  campaigns_retargeting: [],
  countries: [],
  description: 'description',
  hasLBAParent: false,
  isRecency: false,
  items: 0,
  state: 'active',
  type: 'Private',
  created_at: '2020-05-28T09:41:16.106Z',
  updated_at: '2020-05-28T09:41:16.106Z',
}
[POST] /api/audience (multipart)
Creates a new audience, uploading an identifiers file and processing it.

Body params (multipart)

Field	Scope	Type	Description
name	required	string	A name for your audience
description	required	string	A description for your audience
file	required	File	A plain text file with one identifier per line
Additional body params (for Data Partners only)

Field	Scope	Type	Description	Example
cpm	optional	number	CPM: Cost per Mille impressions	{..., "cpm": 0.05, ...}
countries	optional	string	Country of the audience (provide it more than one time to support many countries)	{..., "countries": "FRA", "countries": "ESP", ...}
allowed_organizations	optional	string	Organization ID allowed to use the audience (provide it more than one time to support many organizations)	{..., "allowed_organizations": "id1", "allowed_organizations": "id2", ...}
Success response:

Code	Meaning	Content
201	Success	The created audience model: {id: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/audience' \
       -H 'Authorization: <token>' \
       -F name='Test audience' \
       -F description='This is a test' \
       -F file=@../my/example/file.txt

{
  "id": "...",
  "name": "Test audience",
  "description": "This is a test",
  "items": 169202,
  "allowed_organizations": [],
  "beacon": "https://s3.amazonaws.com/..",
  "beacon_eu": "https://s3.amazonaws.com/..",
  "countries": [],
  "isRecency": boolean,
  "items": 0,
  "state": "active",
  "type": "Private/Time Based...",
  "created_at": "2020-05-18T15:32:29.361Z",
  "updated_at": "2020-05-28T09:41:16.106Z"
}
[POST] /audience/recency (Time Based Audience)
It creates a new recency audience (time based audience), that is, an audience based on the retargeting audience but which includes only the users added to the audiences in the last “X” days. It is only possible to create a new recency audience from a retargeting audience.

Body params

Field	Scope	Type	Description
audienceId	required	string	The id of the retargeting audience
days	required	string	Number of days for the new audience to be created
Success response:

Code	Meaning	Content
201	Success	The id of the created recency audience: {id: ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/audience/recency' \
       -H 'Authorization: <token>' \
       -F audienceId='X' \
       -F days='2' \

{
  "id": "...",
}
[PUT] /api/audience/:id
Updates audience properties. Take in account that this endpoint does not let you replace previous identifiers. If a file is provided, then its content is added to the current audience.

Body params (multipart)

Field	Scope	Type	Description
name	optional	string	A name for your audience
description	optional	string	A description for your audience
file	optional	File	A plain text file with one identifier per line
action	optional	string	“add” to add users or “remove” to remove them. Only useful when file is provided.
Additional body params (for Data Partners only)

Field	Scope	Type	Description	Example
cpm	optional	number	CPM: Cost per Mille impressions	{..., "cpm": 0.05, ...}
countries	optional	string	Country of the audience (provide it more than one time to support many countries)	{..., "countries": "FRA", "countries": "ESP", ...}
allowed_organizations	optional	string	Organization ID allowed to use the audience (provide it more than one time to support many organizations)	{..., "allowed_organizations": "id1", "allowed_organizations": "id2", ...}
Success response:

Code	Meaning	Content
200	Success	The updated audience model: {id: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/audience/<audience_id>' \
       -H 'Authorization: <token>' \
       -X PUT
       -F name='Test audience 2' \
       -F description='This is an updated test'

{
  "id": "...",
  "name": "Test audience 2",
  "description": "This is an updated test",
  "file": "https://s3.amazonaws.com/...",
  "items": 169202,
  "created_at": "2016-05-18T15:32:29.361Z"
}
[PUT] /api/audience/:id/reset
Remove all the identifiers but keeping the audience. This endpoint will reach S3 and delete every file related to the audience from the :id url parameter. :id is an existing audience identifier.

Success response:

Code	Meaning	Content
204	Success empty	No data
Error response:

Code	Meaning
403	Not authorized
500	Something failed removing files
Sample call:

$ curl 'https://api.mediasmart.io/api/audience/:id/reset' \
       -H 'Authorization: <token>'
       -X PUT
Audience Insights
List current audience insights. Insights are not audiences, but simply provide an idea of how different audiences overlap without the need to create a campaign.

[GET] /api/audience-insights
Retrieves all the available audiences insights.

Success response:

Code	Meaning	Content
200	Success	A list of audiences insights: [{...}, {...}, ...]
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call:

$ curl 'https://api.mediasmart.io/api/audience-insights' \
       -H 'Authorization: <token>'

[
  {
    id: 'X',
    name: 'Bla bla bla',
    created_at: '2015-10-02T03:22:00',
    overlapping_audiences: {
      nameOverlappingAudience: {
        id: 'X',
        dataPerDay: {
          [
            ["2020-04-14T", 0],
            ["2020-04-15T", 0],
            ...
          ]
        }
      },
      ...
    },
    main_audience: 'nameMainAudience',
  },
  {
    id: 'Y',
    ...
  },
  ...
]
[GET] /api/audience-insight/:id
Recovers a single audience insight, where :id is an existing audience insight identifier.

Success response:

Code	Meaning	Content
200	Success	Requested campaign body: {id: X, name: Y, ...}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call:

$ curl 'https://api.mediasmart.io/api/audience-insight/:id' \
       -H 'Authorization: <token>'

{
  id: 'X',
  name: 'test',
  organization: 'Y',
  advertiser_name: 'Name',
  overlapping_audiences: {
    nameOverlappingAudience: {
      id: 'X',
      dataPerDay: {
        [
          ["2020-04-14T", 0],
          ["2020-04-15T", 0],
          ...
        ]
      }
    },
    ...
  },
  main_audience: 'nameMainAudience',
  overview: {
    mainAudience: {
      id: 'X',
      name: 'test'
    },
    overlapping_audiences: [
      {
        id: 'X',
        name: 'test',
        isLBA: false
      },
      {
        id: 'X',
        name: 'test',
        isLBA: true
      },
      ...
    ]
  }
}
[POST] /api/audience-insight
Creates a new audience insight, uploading an identifiers file and processing it.

Field	Scope	Type	Description
name	required	string	A name for your audience insight
main_audience	required	string	An id of a Location Based Audience or a Private Audience that has been previously created
overlapping_audiences	required	array of strings	Ids of Location Based Audiences or Private Audiences that have been previously created.
advertiser_name	optional	string	An advertiser name
Success response:

Code	Meaning	Content
201	Success	The created audience insight model: {id: ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/audience-insight' \
       -H 'Authorization: <token>' \
       -F name='Test audience insight' \
       -F main_audience='This is a lba/private audience test' \
       -F overlapping_audiences=['This is a lba/private audience test', ...]

{
  "id": "..."
}
[DELETE] /api/audience-insight/:id
Marks an audience insight as deleted. :id is an existing campaign identifier.

Success response:

Code	Meaning	Content
200	Success	The removed audience insight: {message: 'id'}
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call:

$ curl 'https://api.mediasmart.io/api/audience-insight/:id' \
       -H 'Authorization: <token>'

{ message: 'id' }
Location Based Audiences
These routes let you manage your organization’s location based audiences.

[GET] /api/location_audiences
Retrieves all available location based audiences in your organization.

Success response:

Code	Meaning	Content
200	Success	Objects array: [{areas: '[..]', name: 'name', ...}, ...]
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/location_audiences' \
       -H 'Authorization: <token>'

[
  {
    "areas": <number_of_areas>,
    "cities": [<cities>],
    "regions": [<regions>],
    "countries": [<countries>],
    "created_at": <creation_date>,
    "id": <identifier>,
    "items": <items_count>,
    "name": "<audience_name>",
    "timing": [<time_ranges>],
    "updated_at": "<update_date>",
    "campaigns": [<campaigns>],
    "type": "Location Based",
    "users_limit": <number_of_users_limit>,
  },
  ...
]
[POST] /api/location_audience
Creates a new location based audience.

Body params

Field	Scope	Type	Description
name	required	string	A name for your audience
description	required	string	A description for your audience
countries	required	array	The countries in your audience. It is an array of country codes, this codes have to be retrieved from the dictionary service explained in this documentation.
Additional body params

Field	Scope	Type	Description	Example
regions	optional	array	The regions in your audience. It is an array of region codes, this codes have to be retrieved from the dictionary service explained in this documentation.
cities	optional	array	The cities in your audience. It is an array of city codes, this codes have to be retrieved from the dictionary service explained in this documentation.
precision	optional	string	The precision of the location: low when using IP, medium when using GPS and high when using GPS.
areas	optional	array	The areas where the audiences is based (radius in metres).	[..., {longitude: -4.155308, latitude: 40.6417999, radius: 100}, ...]
timing	optional	array	Time ranges when the audience should be built (similar to campaign schedule one)	{..., timing: [{ monday: true, tuesday: true, started_time_at: "17:00", finished_time_at: "23:00"}, ...], ...}
users_limit	optional	number	Limit of users of the audience. The minimum allowed value is 100000	{..., users_limit: 200000, ...}
timezone	optional	string	Timezone	{..., timezone: "UTC", ...}
Success response:

Code	Meaning	Content
201	Success	The created audience model: {id: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/location_audience' \
       -H 'Authorization: <token>' \
       -X POST \
       --data '{"name": "Audience name", "description": "Audience Description", \
                "cities": ["3117735"], "countries": ["ESP"],\
                "areas": [{"latitude": 40.6417999, "longitude": -4.155308 , "radius": 400 }],\
                "timing": [{"monday": "true", "started_time_at": "17:00", "finished_time_at": "23:00"}]}'

{
    "cities": [
        "3117735"
    ],
    "countries": [
        "ESP"
    ],
    "id": "...",
    "name": "Audience name",
    "precision": "high",
    "regions": [],
    "timing": [{
      monday: true,
      started_time_at: "17:00",
      finished_time_at: "23:00",
    }],
    "description": "Audience Description",
    "areas": [
        {
            "latitude": 40.6417999,
            "longitude": -4.155308,
            "radius": 400
        }
    ],
    "campaigns": [],
    "created_at": "2019-04-219T11:53:22.914Z",
    "started_at": "2019-04-22T11:53:22.914Z",
    "finished_at": "2019-04-30T11:53:22.914Z",
    "timezone": "timezone"
}
[PUT] /api/location_audience/:id
Updates location based audience properties.

Body params

Field	Scope	Type	Description
name	required	string	A name for your audience
description	required	string	A description for your audience
countries	required	array	The countries in your audience. It is an array of country codes, this codes have to be retrieved from the dictionary service explained in this documentation.
Additional body params

Field	Scope	Type	Description	Example
regions	optional	array	The regions in your audience. It is an array of region codes, this codes have to be retrieved from the dictionary service explained in this documentation.
cities	optional	array	The cities in your audience. It is an array of city codes, this codes have to be retrieved from the dictionary service explained in this documentation.
precision	optional	string	The precision of the location: low when using IP, medium when using GPS and high when using GPS.
areas	optional	array	The areas where the audiences is based (radius in metres).	[..., {longitude: -4.155308, latitude: 40.6417999, radius: 100}, ...]
timing	optional	array	Time ranges when the audience should be built (similar to campaign schedule one)	{..., timing: [{ monday: true, tuesday: true, started_time_at: "17:00", finished_time_at: "23:00"}, ...], ...}
Success response:

Code	Meaning	Content
200	Success	The updated audience model: {id: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/location_audience/<audience_id>' \
       -H 'Authorization: <token>' \
       -X PUT
       --data '{"name": "Updated Audience name", "description": "Updated Audience Description", \
                "precision": "low", "cities": ["3117735"], "countries": ["ESP"]\
                "areas": [{"latitude": 40.6417999, "longitude": -4.155308 , "radius": 400 }]'
{
    "cities": [
        "3117735"
    ],
    "countries": [
        "ESP"
    ],
    "id": "...",
    "name": "Updated Audience name",
    "precision": "low",
    "regions": [],
    "timing": [],
    "description": "Updated Audience Description",
    "created_at": "2019-04-17T11:53:22.914Z",
    "areas": [
        {
            "latitude": 40.6417999,
            "longitude": -4.155308,
            "radius": 400
        }
    ],
    "campaigns": [],
    "created_at": "2019-04-219T11:53:22.914Z",
    "started_at": "2019-04-22T11:53:22.914Z",
    "finished_at": "2019-04-30T11:53:22.914Z",
    "timezone": "timezone"
}
[GET] /api/location_audience/:id
Fetches a location based audience.

Success response:

Code	Meaning	Content
200	Success	The location based audience model: {id: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/location_audience/<audience_id>' \
       -H 'Authorization: <token>' \
{
    "cities": [
        "3117735"
    ],
    "countries": [
        "ESP"
    ],
    "id": "...",
    "name": "Updated Audience name",
    "precision": "low",
    "regions": [],
    "timing": [],
    "description": "Updated Audience Description",
    "created_at": "2019-04-17T11:53:22.914Z",
    "areas": [
        {
            "latitude": 40.6417999,
            "longitude": -4.155308,
            "radius": 400
        }
    ],
    "campaigns": [],
    "created_at": "2019-04-219T11:53:22.914Z",
    "started_at": "2019-04-22T11:53:22.914Z",
    "finished_at": "2019-04-30T11:53:22.914Z",
    "timezone": "timezone"
}
Deals
These routes let you manage your organization’s deals.

[GET] /api/organization/:id/deals
Retrieves all existing deals in an organization, where :id is the organization identifier.

Success response:

Code	Meaning	Content
200	Success	An array of objects: [{attr1: 'x', attr2: 'y', ...}]
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/organization/<organization_id>/deals' \
       -H 'Authorization: <token>'

[
  {
     "id" : "<identifier>",
     "key": "<deal_code>",
     "name" : "<deal_name>",
     "description" : "<deal_description>"
     "created_at" : "<iso_date>",
  },
  ...
]
[POST] /api/organization/:id/deal
Creates a new deal in provided organization, where :id is the organization identifier.

Body params

Field	Scope	Type	Description
key	required	string	The deal code ID
name	required	string	A name for your deal
description	optional	string	A description for your deal
Success response:

Code	Meaning	Content
201	Success	The created deal model: {id: ..., key: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
404	Not found.
Sample call

$ curl 'https://api.mediasmart.io/api/organization/<organization_id>/deals' \
       -H 'Authorization: <token>' \
       -d key='MY_DEAL_CODE_ID'
       -d name='Test deal' \
       -d description='This is a test' \

{
  "id": "...",
  "key": ""
  "name": "Test deal",
  "description": "This is a test",
  "created_at": "2016-05-18T15:32:29.361Z"
}
[PUT] /api/organization/:org_id/deals/:id
Updates deal properties, where :org_id is the organization identifier and :id is the deal identifier.

Body params

Field	Scope	Type	Description
key	optional	string	The deal code ID
name	optional	string	A name for your deal
description	optional	string	A description for your deal
Success response:

Code	Meaning	Content
200	Success	The updated deal model: {id: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
404	Not found.
Sample call

$ curl 'https://api.mediasmart.io/api/organization/<organization_id>/deals/<deal_id>' \
       -H 'Authorization: <token>' \
       -X PUT
       -d name='Test deal 2' \
       -d description='This is an updated test'

{
  "id": "...",
  "name": "Test deal 2",
  "description": "This is an updated test",
  ...
}
[DELETE] /api/organization/:org_id/deals/:id
Removes a deal from an organization, where :org_id is the organization identifier, and :id is the deal identifier to be removed.

Success response:

Code	Meaning	Content
200	Success	The removed deal model: {id: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
404	Not found.
Sample call

$ curl 'https://api.mediasmart.io/api/organization/<organization_id>/deals/<deal_id>' \
       -H 'Authorization: <token>' \
       -X DELETE

{
  "id": "...",
  "name": "Test deal 2",
  "description": "This is an updated test",
  ...
}
Geolists
These routes let you manage your organization’s geolists. A geolist is a group of points of interests (POIs) or manual areas. Geolists can be used to target campaigns, for instance.

[GET] /geolists
Retrieves all available geolists in your organization.

Success response:

Code	Meaning	Content
200	Success	List of objects: [{attr1: 'x', attr2: 'y', ...}, ...]
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/geolists' \
       -H 'Authorization: <token>'

[
  {
     "id" : "<identifier>",
     "name" : "<geolist_name>",
  },
  ...
]
[GET] /geolist/:id
Retrieves a geolist from your organization.

Success response:

Code	Meaning	Content
200	Success	Plain object: {attr1: 'x', attr2: 'y', ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/geolist/<id>' \
       -H 'Authorization: <token>'

[
  {
     "id" : "<identifier>",
     "name" : "<geolist_name>",
     "areas": [{
       "latitude": 40.43724322169748,
       "longitude": -3.7026052840879435,
       "radius": 1000,
       "id": "my_area_one",
       "name": "Area One",
       "text": "This is a description of Area One",
     }, ...],
     "countries": ["ESP", ...],
     "cities": ["3124132", ...],
     "regions": [...],
     "created_at" : "<iso_date>",
     "updated_at" : "<iso_date>",
  },
  ...
]
[POST] /geolist
Creates a new geolist.

Body params:

Field	Scope	Type	Description
name	required	string	A name for your list
countries	optional	array	A list of ISO-3 country codes (see dictionary)
regions	optional	array	A list of region codes (see dictionary)
cities	optional	array	A list of city codes (see dictionary)
areas	optional	array of objects	A list of areas
precision	optional	string	A precision (low vs medium vs high)
Success response:

Code	Meaning	Content
201	Success	The created geolist: {id: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/geolist' \
       -H 'Authorization: <token>' \
       -H 'Content-type: application/json'
       --data '{"name": "My first geolist", "countries": ["ESP", "FRA"], "areas": [{"latitude": 40.0556693, "longitude": -2.1254482}], "precision": "low"}'

{
   "name" : "My first geolist",
   "id" : "...",
   "countries" : [
      "ESP",
      "FRA"
   ],
   "areas" : [
      {
         "longitude" : -2.1254482,
         "latitude" : 40.0556693
      }
   ],
   "created_at" : <iso_date>,
   "precision" : "low",
   ...
}
[PUT] /geolist/:id
Updates geolist properties.

Body params:

Field	Scope	Type	Description
name	required	string	A name for your list
countries	optional	array	A list of ISO-3 country codes (see dictionary)
regions	optional	array	A list of region codes (see dictionary)
cities	optional	array	A list of city codes (see dictionary)
areas	optional	array of objects	A list of areas
precision	optional	string	A precision (low vs medium vs high)
Success response:

Code	Meaning	Content
200	Success	The updated list model: {id: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/geolist/<id>' \
       -X PUT \
       -H 'Authorization: <token>' \
       -H 'Content-type: application/json' \
       --data '{"name": "My updated geolist", "areas": [{"longitude": "-2.1254482", "latitude": "40.0556693"}, {"longitude": "-1.1254482", "latitude": "41.0556693"}]}'

{
  "id": "...",
  "name": "My updated geolist",
  "areas" : [
    {
      "longitude" : -2.1254482,
      "latitude" : 40.0556693
    },
    {
      "longitude" : -1.1254482,
      "latitude" : 41.0556693
    }
  ],
  ...
}
Area body
Each area of a geolist is an object with the following attributes:

Field	Scope	Type	Description
latitude	required	number	The latitude of the center
longitude	required	number	The longitude of the center
radius	required	number	The radius of the area
id	optional	string	A simple identifier for reporting
name	optional	string	A short text to define the area
text	optional	string	A full description of the area
Example:

{
  ...
  "areas": [{
    "latitude": 40.43724322169748,
    "longitude": -3.7026052840879435,
    "radius": 1000,
    "id": "my_area_one",
    "name": "Area One",
    "text": "This is a description of Area One",
  }, ...],
  ...
}
Publisher lists
These routes let you manage your organization’s publisher lists.

[GET] /api/publishers/lists
Retrieves all available publisher lists in your organization.

Success response:

Code	Meaning	Content
200	Success	List of objects: [{attr1: 'x', attr2: 'y', ...}, ...]
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/publishers/lists' \
       -H 'Authorization: <token>'

[
  {
     "id" : "<identifier>",
     "name" : "<publisher_list_name>",
     "description" : "<publisher_list_description>"
     "publishers" : <items_count>,
     "created_at" : "<iso_date>",
     "updated_at" : "<iso_date>",
  },
  ...
]
[GET] /api/publishers/list/:id
Retrieves a publisher list from your organization.

Success response:

Code	Meaning	Content
200	Success	Plain object: {attr1: 'x', attr2: 'y', ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/publishers/list/<id>' \
       -H 'Authorization: <token>'

[
  {
     "id" : "<identifier>",
     "name" : "<publisher_list_name>",
     "description" : "<publisher_list_description>"
     "publishers" : <items_count>,
     "created_at" : "<iso_date>",
     "updated_at" : "<iso_date>",
  },
  ...
]
[POST] /api/publishers/list
Creates a new publisher list.

Body params:

Field	Scope	Type	Description
name	required	string	A name for your list
description	optional	string	A description for your list
publishers	required	array	A list of publishers
blacklist_publishers	optional	array	A list of publishers to block
Success response:

Code	Meaning	Content
201	Success	The created publisher list: {id: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/publishers/list' \
       -H 'Authorization: <token>' \
       -H 'Content-type: application/json'
       --data '{"name": "Example", "description": "My first item", "publishers": ["one", "two", "three"]}'

{
  "id": "...",
  "name": "Example",
  "description": "My first item",
  "publishers": ["one", "two", "three"],
  ...
}
[PUT] /api/publishers/list/:id
Updates publishers list properties.

Body params:

Field	Scope	Type	Description
name	optional	string	A name for your list
description	optional	string	A description for your list
publishers	optional	array	A list of publishers
blacklist_publishers	optional	array	A list of publishers to block
Success response:

Code	Meaning	Content
200	Success	The updated list model: {id: ..., name: ..., ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/publishers/list/<id>' \
       -X PUT \
       -H 'Authorization: <token>' \
       -H 'Content-type: application/json' \
       --data '{"name": "New Example", "publishers": ["one", "two", "three", "four"]}'

{
  "id": "...",
  "name": "New Example",
  "description": "My first item",
  "publishers": ["one", "two", "three", "four"],
  ...
}
Organizations
[GET] /api/organizations
Recovers all organizations.

Success response
Code	Meaning	Content
200	Success	Organizations list [{...}, {...}, ...]
Error response
Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
Sample call
$ curl 'https://api.mediasmart.io/api/organizations'
  -H 'Authorization: <token>'

[
  {
     id: ...,
     name: ...,
     image: ...,
     color: ...,
     role: ...,
     ...
  },
  ...
]
[GET] /api/organization/:id
Recovers a single organization, including its children organizations if they exist.

:id is an organization identifier
Success response
Code	Meaning	Content
200	Success	The organization {id: X, name: Y, ...}
Error response
Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call
$ curl 'https://api.mediasmart.io/api/organization/:id'
  -H 'Authorization: <token>'

{
  id: ...,
  name: ...,
  users: [{...}, {...}],
  image: ...,
  ...
},
[POST] /api/organization
Creates a new organization

Body params
Field	Scope	Type	Description	Example
name	required	string	The organization name	{..., name: "xxx", ...}
parent	optional	string	A current organization as parent	{..., parent: "yyy", ...}
seat_id	optional	string	Identifier used for deals	{..., seat_id: 'zzz', ...}
…	…	…	…	…
Success response
Code	Meaning	Content
201	Success	The created organization {id: X, name: Y, ...}
Error response
Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
Sample call
$ curl 'https://api.mediasmart.io/api/organization'
       -X POST --data '{"name": "Hello org"}'
       -H 'Content-type: application/json'
       -H 'Authorization: <token>'

{
  id: ...,
  name: ...,
  seat_id: ...,
  keywords: [...],
  ...
}
Example using curl
$ curl -XPOST "https://api.mediasmart.io/api/organization" \
        -H 'Content-Type: application/json' \
        --data '{"name": "OrgAAA", "color": "#00bcd4", "seat_id": "xxx223"}' \
        -H 'Authorization: <auth_token>'
[PUT] /api/organization/:id
Apply updates over an existing organization.

:id is an organization identifier
Body params
Field	Scope	Type	Description	Example
name	required	string	The organization name	{..., name: "xxx", ...}
seat_id	optional	string	Identifier used for deals	{..., seat_id: 'yyy', ...}
…	…	…	…	…
Success response
Code	Meaning	Content
200	Success	The updated organization {id: X, name: Y, ...}
Error response
Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
404	Not found.
Sample call
$ curl 'https://api.mediasmart.io/api/organization/:id'
       -X PUT --data '{"name": "Updated name"}'
       -H 'Content-type: application/json'
       -H 'Authorization: <token>'

{
  id: ...,
  name: 'Updated name',
  seat_id: ...,
  keywords: [...],
  ...
}
[GET] /api/organization/:id/children
Recovers children organizations of a provided organization ID.

Success response
Code	Meaning	Content
200	Success	Organizations list [{...}, {...}, ...]
Error response
Code	Meaning
401	Not authorized. Rejected token.
403	Forbidden action.
Sample call
$ curl 'https://api.mediasmart.io/api/organization/:id/children'
  -H 'Authorization: <token>'

[
  {
     id: ...,
     name: ...,
     users: [{...}, {...}],
     image: ...,
     parent: {...}
     ...
  },
  ...
]
Organization body
This section describes the Organization model and all its sections and attributes. An organization is a set of first level attributes and some groups with second-level ones inside:

{
  first_level_attribute_1: ...,
  first_level_attribute_2: ...,
  ...
  section_A: {
    second_level_attribute_1: ...,
    second_level_attribute_2: ...,
  },
  section_B: {...},
  ...
}
First level attributes:

Field	Type	Description	Example
accept_googleadx_fee	boolean	Additional Ad serving costs	{..., accept_googleadx_fee: false, ...}
account_manager	string	Account manager responsible for this organization	{..., account_manager: "Peter", ...}
adsquare_id	number	Account manager responsible for this organization	{..., adsquare_id: 99a93c76bd084aee3bd6, ...}
automatic_campaign_name	boolean	Set campaign names automatically	{..., automatic_campaign_name: false, ...}
betatesters	array of objects (defined below)	Users to test the release in production	{..., betatesters: [{...}], ...}
campaign_type	string	Type of campaigns	{..., campaign_type: "branding", ...}
contact	object (defined below)	Contacts	{..., contact: {...}, ...}
conversion_names	object (defined below)	Conversion names	{..., conversion_names: {...}, ...}
currency	string	Currency of the organization	{..., currency: 'usd', ...}
domains	string (read only)	Allowed domain	{..., domains: ["mediasmart.io", ...], ...}
drilldown	string	List of drilldown variables (see dictionary)	{..., drilldown: ["abtag", "age", ...], ...}
empowered_by_liveramp	boolean	The organization has enabled empowered by liveramp and all future campaigns crated within this organization shall have the “Empowered by RampID” option automatically enabled by default	{..., empowered_by_liveramp: true, ...}
global_audience_mapping	boolean	Set the audience mapping value for the entire organization	{..., global_audience_mapping: false, ...}
google_billing_id	string (read only)	Google Billing ID	{..., google_billing_id: "...", ...}
id	string	Organization ID	{..., id: "r8iv21te95tb3z7sjs280n", ...}
invoicing	object (defined below)	Invoicing information	{..., invoicing: {...}, ...}
kpis	boolean	List of kpis variables (see dictionary)	{..., kpis: ["adsquarecost", "wonprice", ...], ...}
language	string	Language for communication. Available languages are defined in the main dictionary as languages.	{..., language: "en", ...}
name	string	The organization name	{..., name: "Hello World", ...}
parent	object	Parent organization	{..., parent: {...}, ...}
pattern_campaign_name	string	Default name pattern	{..., pattern_campaign_name: "...", ...}
seat_id	string (read only)	Seat ID	{..., seat_id: "205326", ...}
sk_postback	string	SKAdNetwork Postback	{..., sk_postback: "http://www.example.com/back.php", ...}
users	array of objects (defined below)	Users that belong to the organization	{..., users: [{...}], ...}
vendor_ids	array of numbers	Vendor IDs	{..., vendor_ids: [6, 9, ...], ...}
Available campaign types are defined as campaign_type in the dictionary:

active
adserving
branding
performance
app_marketing
geolocation
affiliate
vas
video
Second level attributes:

“betatesters” section
Field	Type	Description	Example
id	string	ID	{..., id: "60c74e994d127b49ef5efd87", ...}
name	string	Name	{..., name: "Peter", ...}
“contact” section
Field	Type	Description	Example
commercial	object (defined below)
financial	object (defined below)
legal	object (defined below)
other	array of objects (defined below)
technical	object (defined below)
Available values for contact objects:

Field	Type	Description	Example
email	string	Email	{..., email: "peter@test.com", ...}
name	string	Name	{..., name: "Peter", ...}
phone	string	Phone	{..., phone: "111111111", ...}
Example:

{
  ...
  contact: {
    commercial: {email: "", name: "", phone: ""},
    financial: null,
    legal: null,
    other: [
      {
        email: "",
        name: "",
        phone: ""
      },
      {
        email: "",
        name: "",
        phone: ""
      }
    ],
    technical: null
  },
  ...
}
“conversion_names” section
Field	Type	Description	Example
events2-5	string	Conversion name	{..., conversion_names: {"events2": "test2", "events3": "test3"}, ...}
“invoicing” section
All fields in this section are read only.

Field	Type	Description	Example
address	string	Billing Address	{..., address: "Any Street", ...}
breakdown	array of strings	Breakdown	{..., breakdown: ["campaign", "..."], ...}
city	string	Breakdown	{..., city: "Madrid", ...}
country	string	Breakdown	{..., country: "Spain", ...}
currency_invoicing	string	Invoicing currency	{..., currency_invoicing: "eur", ...}
customer_name	string	Customer name	{..., customer_name: "Peter S.L.", ...}
vat_number	string	VAT Number	{..., vat_number: "ES858164427C41", ...}
zipcode	string	ZIP code	{..., zipcode: "28047", ...}
Available values for breakdown object:

campaign
countrycode
organization
deal
Example:

{
  ...
  invoicing: {
    address: 'Any Street',
    breakdown: ['campaign', 'countrycode', 'deal'],
    city: 'Madrid',
    country: 'Spain',
    currency_invoicing: 'eur',
    rule,
    ...
  },
  ...
}
“users” section
Field	Type	Description	Example
daystats_drilldown	array of strings	Daystats Drilldown variables. Available daystats drilldown variables are defined in the main dictionary as daystats_drilldown.	{..., daystats_drilldown: ["Won", "..."], ...}
daystats_kpis	array of strings	Daystats KPIs. Available daystats KPIs are defined in the main dictionary as daystats_kpis.	{..., daystats_kpis: ["Bids", "..."], ...}
drilldown	array of strings	Drilldown variables. Available drilldown variables are defined in the main dictionary as drilldown.	{..., drilldown: ["abtag", "..."], ...}
email	string	Email	{..., email: "peter@test.com", ...}
image	string	Image	{..., image: "https://www.learningcontainer.com/sample-png-image-for-testing/, ...}
kpis	array of strings	KPIs. Available KPIs variables are defined in the main dictionary as kpis.	{..., kpis: ["bids", "..."], ...}
name	string	Name	{..., name: "Peter", ...}
password	string	Password	{..., password: "********", ...}
role	string	Role	{..., role: "viewer" ...}
username	string	Username	{..., username: "Peter Pan", ...}
Available user roles are defined as roles in the dictionary:

adexchange
advertiser
audience_manager
creative_manager
editor
owner
viewer
Betatesters
These routes let you manage your organization’s betatester users and IPs.

[GET] /api/organization/:id/betatesters
Retrieves all existing betatesters in an organization, where :id is the organization identifier.

Success response:

Code	Meaning	Content
200	Success	List of betatester instances: [{attr1: 'x', attr2: 'y', ...}]
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/organization/<organization_id>/betatesters' \
       -H 'Authorization: <token>'

[
  {
     "id" : "<native_identifier_or_IP>",
     "name" : "<betatester_name>",
  },
  ...
]
[POST] /api/organization/:id/betatesters
Creates a new betatester in the provided organization, where :id is the organization identifier.

Body params

Field	Scope	Type	Description
id	required	string	The betatester native identifier or IP
name	required	string	A descriptive name for your betatester
Success response:

Code	Meaning	Content
201	Success	The created betatester model: {id: ..., name: ...}
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
404	Not found.
Sample call

$ curl 'https://api.mediasmart.io/api/organization/<organization_id>/betatesters' \
       -H 'Authorization: <token>' \
       -d id='34.123.89.101'
       -d name='My office IP' \

{
  "id": "34.123.89.101",
  "name": "My office IP",
}
[DELETE] /api/organization/:id/betatesters
Removes a betatester from an organization, where :id is the organization identifier.

Body params

Field	Scope	Type	Description
id	required	string	The betatester native identifier or IP
Success response:

Code	Meaning	Content
204	Success	No data
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
404	Not found.
Sample call

$ curl 'https://api.mediasmart.io/api/organization/<organization_id>/betatesters' \
       -H 'Authorization: <token>' \
       -X DELETE
       -d id='34.123.89.101'
Campaign info
This route let you download JSON files populated with some information about campaigns that cannot be found on the analytics section. You will be able to check the number of unique users and unique households of each campaigns. Also, in Footfall campaigns, you can find information about how many attributed visits each POI has had and about the distance and time from impression to attributed visit.

[GET] /v2/analytics/unique-users
Retrieves the number of unique users and unique households for a given date and campaign. This can be based on impression, click, events1, events2, events3, events4 or events5.

URL params:

Field	Scope	Type	Description	Example
campaign	required	string	Campaign identifier to consider	campaign=id1
from	required	date	Date to specify the start of a date range to download. Needs the parameter to also in the request	from=2024-05-01
to	required	date	Date to specify the end of a date range to download . Needs the parameter from also in the request	to=2024-05-14
kpi	required	list	The kpi on which users are based .	kpi=impression
Available KPIs are: impression, click, events1, events2, events3, events4, events5.

Success response:

Code	Meaning	Content
200	Success	A json file with the requested data
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Permission denied.
400	Bad request.
Sample call

$ curl 'https://api.mediasmart.io/v2/analytics/unique-users?campaign=eikpryzpdjclqk1qmihhz9tbffu41p&from=2024-05-01&to=2024-05-14&kpi=impression' \
       -H 'Authorization: <token>'
[GET] /v2/analytics/top-pois
Retrieves the number of attributed visits pero POI for a given date and campaign.

URL params:

Field	Scope	Type	Description	Example
campaign	required	string	Campaign identifier to consider	campaign=id1
from	required	date	Date to specify the start of a date range to download. Needs the parameter to also in the request	from=2024-05-01
to	required	date	Date to specify the end of a date range to download . Needs the parameter from also in the request	to=2024-05-14
Success response:

Code	Meaning	Content
200	Success	A json file with the requested data
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Permission denied.
400	Bad request.
Sample call

$ curl 'https://api.mediasmart.io/v2/analytics/top-pois?campaign=vv5r94nvtsnxocraptkfv3whx7vzmj&from=2024-05-01&to=2024-05-14' \
       -H 'Authorization: <token>'
[GET] /v2/analytics/distance-time
Retrieves the information about the distance between where the impression was served and where the conversion took place. Also, information about the time between when the impression was served and when the conversion took place.

URL params:

Field	Scope	Type	Description	Example
campaign	required	string	Campaign identifier to consider	campaign=id1
from	required	date	Date to specify the start of a date range to download. Needs the parameter to also in the request	from=2024-05-01
to	required	date	Date to specify the end of a date range to download . Needs the parameter from also in the request	to=2024-05-14
kpi	required	list	In this case it only makes sense for events1 (attributed visit) .	kpi=events1
Success response:

Code	Meaning	Content
200	Success	A json file with the requested data
Error response:

Code	Meaning
401	Not authorized. Rejected token.
403	Permission denied.
400	Bad request.
Sample call

$ curl 'https://api.mediasmart.io/v2/analytics/distance-time?campaign=difhoub78eq1r3mrs3xdaslqgwjcna2k&from=2024-05-01&to=2024-05-14&kpi=events1' \
       -H 'Authorization: <token>'
Session Data
This route let you download JSON files populated with event data (impression, click , conversion 1 to 5 or video events). If you are interested in this kind of storage, you can find more info here

[GET] /api/session-data
Retrieves all session data available files in your organization for a given date and/or campaigns.

URL params:

Field	Scope	Type	Description	Example
date	optional	date	Date to be download	date=2017-03-30
from	optional	date	Date to specify the start of a date range to download. Needs the parameter to also in the request	from=2018-12-01
to	optional	date	Date to specify the end of a date range to download . Needs the parameter from also in the request	to=2018-12-05
campaigns	optional	list	Campaign identifiers to consider	campaigns=id1,id2,id3
If no date is specified, then the current day will be used. If from, to and date are specified, the date parameter will be ignored and from and to will be taken into account.

Success response:

Code	Meaning	Content
200	Success	A zip file with all the compressed json files for the specified date
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/session-data?date=2017-03-15' \
       -H 'Authorization: <token>'
[GET] /api/session-data/fetch
Retrieves all session data available files in your organization that have been requested before using /api/session-data route. It is important to notice that the parameters used in the /api/session-data route must be sent also in this request.

URL params:

Field	Scope	Type	Description	Example
date	optional	date	Date to be download	date=2017-03-30
from	optional	date	Date to specify the start of a date range to download. Needs the parameter to also in the request	from=2018-12-01
to	optional	date	Date to specify the end of a date range to download . Needs the parameter from also in the request	to=2018-12-05
campaigns	optional	list	Campaign identifiers to consider	campaigns=id1,id2,id3
If no date is specified, then the current day will be used. If from, to and date are specified, the date parameter will be ignored and from and to will be taken into account.

Success response:

Code	Meaning	Content
200	Success	An URL to download the generated .zip file with the session data.
Error response:

Code	Meaning
401	Not authenticated.
403	Not authorized.
Sample call

$ curl 'https://api.mediasmart.io/api/session-data/fetch?date=2017-03-15' \
       -H 'Authorization: <token>'



API quotas
We've implemented two quota limits for our console/api requests to ensure a high-quality service for all clients:

10 concurrent requests. Example: if you're running 10 simultaneous reports, a new one will be rejected until one of them finishes.

128 requests per minute. Example: if you've done 128 requests in the current minute, all new requests until the next minute will be rejected. Any exceeding requests will be temporarily rejected. 

Ports / Servers
All requests must be thrown against one of the following servers:

Production environment: api.mediasmart.io (port 80)

Testing environment: apitest.mediasmart.io (port 80)