Included in this repository is a trading algorithm that screens equities monthly based on predetermined factors and then determines our position based on a trend-following strategy. 
Then each equity is automatically hedged with either a put or call option depending on our position (If the option is available for trading/liquid enough)
All of the programs are written in python through QuantConnect's API. All of the code above was created and executed through QuantConnect's browser IDE however could also be run locally if one so desires.

Moving forward, I hope to incorporate pricing formulas such as the Black-Scholes to determine the best-priced option and include the degree of hedging present in the portfolio. 
This would allow the user to hedge their portfolio 100% or 80% or possibly only the 20% most volatile assets. 
