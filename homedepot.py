from datetime import datetime, timedelta, timezone
import json
import sys

import requests_cache
from pyquery import PyQuery

NOW = datetime.now(timezone.utc)


# Web API call wrappers
session = requests_cache.CachedSession(
    "partcad_homedepot",
    use_cache_dir=True,  # Save files in the default user cache dir
    cache_control=True,  # Use Cache-Control response headers for expiration, if available
    expire_after=timedelta(days=1),  # Otherwise expire responses after one day
    allowable_codes=[
        200,
        400,
    ],  # Cache 400 responses as a solemn reminder of your failures
    allowable_methods=["GET", "POST"],  # Cache whatever HTTP methods you want
)

headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-GB,en;q=0.9",
    "priority": "u=0, i",
    "referer": "https://www.google.com/",
    "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "cross-site",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1"
}

cart_headers = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-GB,en;q=0.9",
    "content-length": "9019",
    "origin": "https://www.homedepot.com",
    "priority": "u=1, i",
    "referer": "https://www.homedepot.com/",
    "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "x-current-url": "/cart/atc",
    "x-debug": "false",
    "x-experience-name": "cart",
    "x-hd-dc": "origin",
    "x-thd-customer-token": ""
}

if not "request" in globals():
    request = {
        "api": "caps"
    }
cookies_dict = {}
cookies_string = ""

def get_cookies(cookie_jar, cookie_dict):
    """
    Refreshing cookies after each request to avoid bot detection
    """
    for cookie in cookie_jar:
        cookie_dict[cookie.name] = cookie.value
    return cookie_dict

def get_product_id(sku):
    """
    Retrieve the product ID corresponding to the provided SKU from Home Depot's website.

    Args:
        sku (str): The SKU of the product to lookup.

    Returns:
        str: The product ID extracted from the product URL.

    Raises:
        Exception: If the product ID cannot be retrieved.
    """
    global headers
    global partcad_version
    global cookies_string
    global cookies_dict

    url = f"https://www.homedepot.com/s/{sku}"

    response = session.get(url, headers={**headers, "user-agent": "partcad/" + partcad_version, "cookie": cookies_string})

    if response.url == url:
        try:
            pq = PyQuery(response.text)
            
            # Find the <script> tag with type="application/ld+json"
            script_tag = pq('script[type="application/ld+json"]')

            data = json.loads(script_tag.text())
            url = data[0]["mainEntity"]["offers"]["itemOffered"][0]["offers"]["url"]
        except:
            sys.stderr.write(
                "Failed to get Product ID from SKU\n"
            )
            raise Exception("Failed to get Product ID from SKU")
    else:
        url = response.url

    cookies_dict = get_cookies(response.cookies, cookies_dict)
    cookies_string = ""
    for cookie in cookies_dict.items():
        cookies_string += f"{cookie[0]}={cookie[1]};"
    cookies_string = cookies_string[:-1]

    return url.split("/")[-1]


def get_quote(product_id, item_count):
    """
    Add a specified product and quantity to the Home Depot online cart and retrieve the cart details.

    Args:
        product_id (str): The ID of the product to add to the cart.
        item_count (int): The quantity of the product to add.

    Returns:
        dict: Cart details from the Home Depot API response.

    Raises:
        Exception: If the API call fails.
    """
    global cart_headers
    global partcad_version
    global cookies_dict
    global cookies_string

    url = "https://apionline.homedepot.com/federation-gateway/graphql?opname=addToCart"

    body = {
        "operationName": "addToCart",
        "variables": {
            "cartRequest": {
                "filterItem": True,
                "localization": {
                    "primaryStoreId": 1710
                },
                "items": {
                    "pickup": [
                        {
                            "itemId": product_id,
                            "quantity": f"{item_count}",
                            "type": "bopis",
                            "location": "1710"
                        }
                    ]
                }
            },
            "requestContext": {
                "isBrandPricingPolicyCompliant": False
            }
        },
        "query": "mutation addToCart($cartRequest: CartInfoRequest!, $requestContext: RequestContext) {\n  addToCart(cartRequest: $cartRequest, requestContext: $requestContext) {\n    cartId\n    itemCount\n    customer {\n      userId\n      customerId\n      type\n      addresses {\n        id\n        firstName\n        lastName\n        addressLine1\n        addressLine2\n        zipCode\n        state\n        country\n        county\n        phone\n        phoneNumber\n        hideCVV\n        city\n        type\n        default\n        primaryPhoneId\n        addressIdentifier\n        businessAddress\n        category\n        __typename\n      }\n      __typename\n    }\n    payments {\n      emailId\n      amountCharged\n      cardBrand\n      maskedCardNumber\n      xref\n      paymentId\n      type\n      addressIds\n      __typename\n    }\n    rentalEstimate {\n      tools {\n        categoryCode\n        subCategoryCode\n        deposit\n        feeTotal\n        taxTotal\n        taxPercentage\n        fees {\n          type\n          value\n          taxTotal\n          taxPercentage\n          percentage\n          taxes {\n            type\n            value\n            percentage\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    messages {\n      type\n      messageCategoryType\n      correlationId\n      correlationType\n      longDesc\n      shortDesc\n      __typename\n    }\n    items {\n      id\n      quantity\n      product {\n        itemId\n        addons {\n          installation\n          termLength\n          type\n          price\n          totalPrice\n          quantity\n          itemId\n          id\n          category\n          description\n          detailsUrl\n          selected\n          storeId\n          protectionPlanParentId\n          brandName\n          configAttr\n          descriptiveAttributes\n          __typename\n        }\n        info {\n          returnable\n          quantityLimit\n          minimumOrderQuantity\n          inStoreReturnEligibility\n          paintBrand\n          paintDetails {\n            configId\n            colorName\n            rgb {\n              red\n              blue\n              green\n              __typename\n            }\n            __typename\n          }\n          __typename\n        }\n        specificationGroup {\n          specTitle\n          specifications {\n            specName\n            specValue\n            __typename\n          }\n          __typename\n        }\n        pricing {\n          value\n          original\n          total\n          totalWithNoDiscount\n          valueStartDate\n          valueEndDate\n          type\n          discount {\n            percentOff\n            dollarOff\n            __typename\n          }\n          clearance {\n            value\n            dollarOff\n            percentageOff\n            __typename\n          }\n          mapDetail {\n            mapPolicy\n            __typename\n          }\n          __typename\n        }\n        media {\n          images {\n            url\n            type\n            subType\n            sizes\n            hotspots\n            altText\n            __typename\n          }\n          __typename\n        }\n        identifiers {\n          configId\n          editUrl\n          copyUrl\n          productCategory\n          leadTime\n          canonicalUrl\n          brandName\n          itemId\n          modelNumber\n          productLabel\n          storeSkuNumber\n          skuClassification\n          productType\n          isSuperSku\n          shipType\n          partNumber\n          fromName\n          toName\n          message\n          deliveryMethod\n          recipientEmail\n          __typename\n        }\n        fulfillment {\n          backordered\n          backorderedShipDate\n          bossExcludedShipStates\n          excludedShipStates\n          seasonStatusEligible\n          anchorStoreStatus\n          anchorStoreStatusType\n          sthExcludedShipState\n          bossExcludedShipState\n          onlineStoreStatus\n          onlineStoreStatusType\n          inStoreAssemblyEligible\n          fulfillmentOptions {\n            type\n            fulfillable\n            services {\n              type\n              expectedArrival\n              hasFreeShipping\n              estimatedDelivery\n              freeDeliveryThreshold\n              deliveryCharge\n              selected\n              optimalFulfillment\n              dynamicEta {\n                hours\n                minutes\n                __typename\n              }\n              deliveryDates {\n                startDate\n                endDate\n                __typename\n              }\n              totalCharge\n              deliveryTimeline\n              locations {\n                isAnchor\n                locationId\n                zipCode\n                curbsidePickupFlag\n                isBuyInStoreCheckNearBy\n                distance\n                storeName\n                city\n                state\n                storePhone\n                type\n                inventory {\n                  isOutOfStock\n                  quantity\n                  isInStock\n                  isUnavailable\n                  isLimitedQuantity\n                  backordered\n                  maxAllowedBopisQty\n                  minAllowedBopisQty\n                  __typename\n                }\n                storeHours {\n                  monday {\n                    open\n                    close\n                    __typename\n                  }\n                  tuesday {\n                    open\n                    close\n                    __typename\n                  }\n                  wednesday {\n                    open\n                    close\n                    __typename\n                  }\n                  thursday {\n                    open\n                    close\n                    __typename\n                  }\n                  friday {\n                    open\n                    close\n                    __typename\n                  }\n                  saturday {\n                    open\n                    close\n                    __typename\n                  }\n                  sunday {\n                    open\n                    close\n                    __typename\n                  }\n                  storeTimeZone\n                  __typename\n                }\n                __typename\n              }\n              isBossDominant\n              __typename\n            }\n            addressId\n            __typename\n          }\n          __typename\n        }\n        dataSources\n        attributes {\n          name\n          value\n          sequenceNumber\n          __typename\n        }\n        essentialAccessories\n        __typename\n      }\n      selectedFulfillment\n      __typename\n    }\n    itemGrouping {\n      byFulfillment {\n        appliance {\n          type\n          zipCode\n          ids\n          __typename\n        }\n        pickup {\n          location {\n            curbsidePickupFlag\n            storeName\n            __typename\n          }\n          ids\n          __typename\n        }\n        delivery {\n          grouping {\n            type\n            ids\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    descriptiveAttr {\n      cartType\n      paypalExpress\n      paymentOnHold\n      isIcEnabled\n      displayIcOption\n      poJobName\n      hasSubscriptionItems\n      maxCartPriceContributor\n      uniqueItemCount\n      __typename\n    }\n    promos {\n      desc\n      longDesc\n      type\n      tag\n      appliedDisc\n      promoCode\n      restrictions {\n        paymentType\n        __typename\n      }\n      message {\n        type\n        messageCategoryType\n        correlationId\n        correlationType\n        longDesc\n        shortDesc\n        __typename\n      }\n      attached\n      promoItems {\n        appliedDiscount\n        appliedOn\n        __typename\n      }\n      __typename\n    }\n    localization {\n      primaryStoreId\n      deliveryZip\n      deliveryStateCode\n      __typename\n    }\n    totals {\n      total\n      totalDiscount\n      totalWithNoDiscount\n      deliveryCharge\n      applianceDeliveryCharge\n      type\n      adjustments {\n        amount\n        type\n        __typename\n      }\n      plccEligibleTotal\n      __typename\n    }\n    __typename\n  }\n}"
    }

    cart = session.post(url, headers={**cart_headers, "cookie": cookies_string, "user-agent": "partcad/" + partcad_version}, json=body, cookies=cookies_dict)
    if cart.status_code != 200:
        raise Exception("Failed to add item to cart")
    
    cookies_dict = get_cookies(cart.cookies, cookies_dict)
    cookies_string = ""
    for cookie in cookies_dict.items():
        cookies_string += f"{cookie[0]}={cookie[1]};"
    cookies_string = cookies_string[:-1]

    try:
        return cart.json()["data"]["addToCart"]
    except Exception as e:
        global exception
        exception = e

        sys.stderr.write(
            "Failed to parse response - STATUS CODE: %d - PRODUCT ID: %s\n"
            % (cart.status_code, str(product_id))
        )
    return {}

if __name__ == "caps":
    raise Exception("Not suported by stores")

elif __name__ == "avail":
    vendor = request.get("vendor", None)
    sku = request.get("sku", None)

    if vendor == "homedepot":
        output = {
            "available": True,
        }
    else:
        output = {
            "available": False,
        }

elif __name__ == "quote":
    parts = request["cart"]["parts"]
    cart = {}
    for part_spec in parts.values():
        sku = part_spec.get("sku", "").replace("-", "")
        count_per_sku = part_spec["count_per_sku"]
        count = part_spec["count"]
        item_count = (count + count_per_sku - 1) // count_per_sku
        partcad_version = request["partcad_version"]
        product_id = get_product_id(sku)
        cart = get_quote(product_id, item_count)
        # sys.stderr.write("CARD ID: " + cart["cartId"] + "\n")

    output = {
        "qos": request["cart"]["qos"],
        "price": cart.get("totals", {}).get("total", 0),
        "expire": (NOW + timedelta(hours=1)).timestamp(),
        "cartId": cart.get("cartId", None),
        "etaMin": (NOW + timedelta(hours=1)).timestamp(),
        "etaMax": (NOW + timedelta(hours=2)).timestamp(),
    }

elif __name__ == "order":
    raise Exception("Not implemented")

else:
    raise Exception("Unknown API: {}".format(__name__))
