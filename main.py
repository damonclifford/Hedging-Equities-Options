import OptionsUniverse # Our Options Universe
import OptionsAlpha #Our options Alpha 

class Options (QCAlgorithm):
    
    def Initialize(self):
        self.SetStartDate(2019,1,4)  
        self.SetEndDate(2019,12,4)
        self.SetCash(100000)  # Set Strategy Cash
        self.SetTimeZone(TimeZones.Chicago)
       
        self.SetSecurityInitializer(lambda s: s.SetMarketPrice(self.GetLastKnownPrice(s))) 
       
        self.AddUniverseSelection(OptionsUniverse.universe()) #Calls Universe class, returns equities and underlying alphas
    
        self.UniverseSettings.Resolution = Resolution.Minute #Minute resolution for options
        self.UniverseSettings.DataNormalizationMode=DataNormalizationMode.Raw #how data goes into alg
        self.UniverseSettings.FillForward = True #Fill in empty data will next price
        self.UniverseSettings.ExtendedMarketHours = False #Does not takes in account after hours data
        self.UniverseSettings.MinimumTimeInUniverse = 1 # each equity has to spend at least 1 hour in universe
        self.UniverseSettings.Leverage=2 #Set's 2 times leverage
        self.Settings.FreePortfolioValuePercentage = 0.5
      
       
        self.AddAlpha(OptionsAlpha.alpha()) #Emits insights on equities and send automatic market orders on options

         # we do not want to rebalance on insight changes
        self.Settings.RebalancePortfolioOnInsightChanges = False;
        # we want to rebalance only on security changes
        self.Settings.RebalancePortfolioOnSecurityChanges = False;
        #Set's equal weighting for all of our insights (equities) in our algorithm
        self.SetPortfolioConstruction(EqualWeightingPortfolioConstructionModel())


        self.SetRiskManagement(NullRiskManagementModel())
        # Does not set any risk parameters
        
        self.SetExecution(ImmediateExecutionModel())
        
    def OnData(self, slice):
      if self.IsWarmingUp: return