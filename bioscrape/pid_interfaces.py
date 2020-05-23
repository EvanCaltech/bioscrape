from bioscrape.inference import DeterministicLikelihood as DLL
from bioscrape.inference import StochasticTrajectoriesLikelihood as STLL
from bioscrape.inference import StochasticTrajectories
from bioscrape.inference import BulkData
import warnings
import numpy as np

class PIDInterface():
    '''
    PID Interface : Parameter identification interface.
    Super class to create parameter identification (PID) interfaces. Two PID interfaces currently implemented: 
    Deterministic and Stochastic inference using time-series data.
    To add a new PIDInterface - simply add a new subclass of this parent class with your desired 
    log-likelihood functions. You can even have your own check_prior function in that class if you do not 
    prefer to use the built in priors with this package.
    '''
    def __init__(self, params_to_estimate, M, prior):
        '''
        Parent class for all PID interfaces.
        Arguments:
        * `params_to_estimate` : List of parameter names to be estimated 
        * `M` : The bioscrape Model object to use for inference
        * `prior` : A dictionary specifying prior distribution. 
        Two built-in prior functions are `uniform_prior` and `gaussian_prior`.
        Each prior has its own syntax for accepting the distribution parameters in the dictionary. 
        New priors may be added. The suggested format for prior dictionaries:
        prior_dict = {'parameter_name': ['prior_name', prior_distribution_parameters]}
        For built-in uniform prior, use {'parameter_name':['uniform', lower_bound, upper_bound]}
        For built-in gaussian prior, use {'parameter_name':['gaussian', mean, standard_deviation, probability threshold]}

        New PID interfaces can be added by creating child classes of PIDInterface class as shown for 
        Built-in PID interfaces : `StochasticInference` and `DeterministicInference`
        '''
        self.params_to_estimate = params_to_estimate
        self.M = M
        self.prior = prior
        return
    
    def check_prior(self, params_dict):
        '''
        To add new prior functions: simply add a new function similar to ones that exist and then 
        call it here.
        '''
        lp = 0.0
        for key,value in params_dict.items():
            prior_type = self.prior[key][0]
            if prior_type == 'uniform':
                lp += self.uniform_prior(key, value)
            elif prior_type == 'gaussian':
                lp += self.gaussian_prior(key, value)
            else:
                raise ValueError('Prior type undefined.')
        return lp

    def uniform_prior(self, param_name, param_value):
        '''
        Check if given param_value is valid according to the prior distribution.
        Returns False if the param_value is invalid. param_name is used to look for 
        the parameter in the prior dictionary.
        '''
        prior_dict = self.prior
        if prior_dict is None:
            raise ValueError('No prior found')
        if len(prior_dict[param_name]) != 3:
            raise ValueError('For uniform distribution, the prior dictionary entry must be : [prior_type, lower_bound, upper_bound]')
        lower_bound = prior_dict[param_name][1]
        upper_bound = prior_dict[param_name][2]
        if param_value > upper_bound or param_value < lower_bound:
            return np.inf
        else:
            return 0.0

    def gaussian_prior(self, param_name, param_value):
    # def gaussian_prior(self, params_dict):
        '''
        Check if given param_value is valid according to the prior distribution.
        Returns False if the param_value is invalid. 
        '''
        prior_dict = self.prior
        if prior_dict is None:
            raise ValueError('No prior found')
        if len(prior_dict[param_name]) != 4:
            raise ValueError('For Gaussian distribution, the dictionary entry must be : [prior_type, mean, std_dev, probability_threshold]')
        mu = prior_dict[param_name][1]
        sigma = prior_dict[param_name][2]
        prob_threshold = prior_dict[param_name][3]
        # Check if value lies is a valid sample of (mu, sigma) normal distribution
        # Using probability density function for normal distribution
        # Using scipy.stats.norm has overhead that affects speed up to 2x
        prob = 1/(np.sqrt(2*np.pi) * sigma) * np.exp((-0.5*param_value - mu)**2/sigma**2)
        if prob > 1:
            warnings.warn('Probability greater than 1 while checking Gaussian prior! Something is wrong...')
        if prob < prob_threshold:
            return np.inf
        else:
            return 0.0

# Add a new class similar to this to create new interfaces.
class StochasticInference(PIDInterface):
    def __init__(self, params_to_estimate, M, prior):
        super().__init__(params_to_estimate, M, prior)
        return

    def get_likelihood_function(self, params_values, data, timepoints, measurements, initial_conditions, norm_order = 2, N_simulations = 3, debug = False):
        M = self.M
        params_dict = {}
        for key, p in zip(self.params_to_estimate, params_values):
            params_dict[key] = p
        # Check prior
        lp = self.check_prior(params_dict)
        if not np.isfinite(lp):
            return -np.inf
        N = np.shape(data)[0]
        if debug:
            print('The timepoints shape is {0}'.format(np.shape(timepoints)))
            print('The data shape is {0}'.format(np.shape(data)))
            print('The measurmenets is {0}'.format(measurements))
            print('The N is {0}'.format(N))
        dataStoch = StochasticTrajectories(np.array(timepoints), data, measurements, N)
        #If there are multiple initial conditions in a data-set, should correspond to multiple initial conditions for inference.
        #Note len(initial_conditions) must be equal to the number of trajectories N
        LL_stoch = STLL(model = M, init_state = initial_conditions,
        data = dataStoch, N_simulations = N_simulations, norm_order = norm_order)
        # Set params here and return the likelihood object.
        if LL_stoch:
            LL_stoch.set_init_params(params_dict)
            LL_stoch_cost = LL_stoch.py_log_likelihood()
            ln_prob = lp + LL_stoch_cost
            return ln_prob
       
# Add a new class similar to this to create new interfaces.
class DeterministicInference(PIDInterface):
    def __init__(self, params_to_estimate, M, prior):
        super().__init__(params_to_estimate, M, prior)
        return

    def get_likelihood_function(self, params_values, data, timepoints, measurements, initial_conditions, norm_order = 2, debug = False):
        M = self.M
        params_dict = {}
        # params_exp = np.exp(log_params)
        for key, p in zip(self.params_to_estimate, params_values):
            params_dict[key] = p
        # Check prior
        lp = 0
        lp = self.check_prior(params_dict)
        if not np.isfinite(lp):
            return -np.inf
        N = np.shape(data)[0]
        #Ceate Likelihood objects:
        # Create a data Objects
        # In this case the timepoints should be a list of timepoints vectors for each iteration
        dataDet = BulkData(np.array(timepoints), data, measurements, N)
        #If there are multiple initial conditions in a data-set, should correspond to multiple initial conditions for inference.
        #Note len(initial_conditions) must be equal to the number of trajectories N
        if debug:
            print('The timepoints shape is {0}'.format(np.shape(timepoints)))
            print('The data shape is {0}'.format(np.shape(data)))
            print('The measurmenets is {0}'.format(measurements))
            print('The N is {0}'.format(N))
        # TODO: Initial conditions not going through correctly?
        # TODO: Need to fix how multiple initial conditions will be handled because in pid_interfaces only one at a time can go through.
        LL_det = DLL(model = M, init_state = initial_conditions,
        data = dataDet, norm_order = norm_order)
        #Multiple samples with a single initial only require a single initial condition.
        # Set params here and return the likelihood object.
        if LL_det:
            LL_det.set_init_params(params_dict)
            LL_det_cost = LL_det.py_log_likelihood()
            ln_prob = lp + LL_det_cost
            return ln_prob
        




