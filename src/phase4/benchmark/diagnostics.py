"""Diagnostics that test the explanations behind the benchmark."""
import numpy as np, pandas as pd, warnings
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import spearmanr
from sklearn.decomposition import PCA
from sklearn.kernel_ridge import KernelRidge
from sklearn.linear_model import Ridge, HuberRegressor
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.neighbors import KNeighborsRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR, LinearSVR
from benchmark_models import OUT, load, F2A, T2G
warnings.filterwarnings('ignore')
ta, Xt, _ = load('ta_fc.csv', 'subcat_label'); fr, Xf, _ = load('fr_fc.csv', 'category')
X = np.vstack([Xt, Xf]); price = np.concatenate([ta.price, fr.price])
chan = np.array(['classified']*len(ta) + ['friperie']*len(fr))
logp = np.log(price); y = logp - np.array([logp[chan==c].mean() for c in chan])
S = X@X.T; np.fill_diagonal(S,0); S[chan[:,None]!=chan[None,:]]=0
_, g = connected_components(csr_matrix(S>=.99), directed=False)
def folds(seed):
    r=np.random.default_rng(seed); gid=r.permutation(np.unique(g))
    for b in np.array_split(gid,5):
        te=np.isin(g,b); yield np.where(~te)[0], np.where(te)[0]
def evaluate(make, seeds=(0,1,2)):
    P=np.zeros((len(seeds),len(y)))
    for si,s in enumerate(seeds):
        for tr,te in folds(s):
            m=make(); m.fit(X[tr],y[tr]) if not isinstance(m,GridSearchCV) else m.fit(X[tr],y[tr],groups=g[tr])
            P[si,te]=m.predict(X[te])
    out={}
    for ch in ['friperie','classified']:
        k=chan==ch
        out[ch+'_rho']=np.mean([spearmanr(P[s,k],y[k]).statistic for s in range(len(seeds))])
        out[ch+'_err']=np.mean([np.exp(np.abs(P[s,k]-y[k]).mean()) for s in range(len(seeds))])
        out[ch+'_pred_sd']=P[:,k].std(1).mean()
    out['true_sd_fr']=y[chan=='friperie'].std(); out['true_sd_cl']=y[chan=='classified'].std()
    return out
inner=GroupKFold(3)
def tuned(est,grid): return lambda: GridSearchCV(est,grid,cv=inner,scoring='neg_mean_absolute_error',n_jobs=2)
res={}
print('--- 1. ridge alpha curve', flush=True)
for a in [1,10,100,1000,10000,100000]:
    res[f'ridge alpha={a}']=evaluate(lambda a=a: make_pipeline(StandardScaler(),Ridge(alpha=a)))
print('--- 2. loss x kernel', flush=True)
res['squared loss, linear (ridge a=1000)']=res['ridge alpha=1000']
res['squared loss, RBF (kernel ridge)']=evaluate(tuned(make_pipeline(StandardScaler(),KernelRidge(kernel='rbf',gamma=1/512)),{'kernelridge__alpha':[0.3,1,3,10]}))
res['robust loss, linear (linear SVR)']=evaluate(tuned(make_pipeline(StandardScaler(),LinearSVR(epsilon=0.1,max_iter=20000,dual='auto')),{'linearsvr__C':[1e-4,3e-4,1e-3,3e-3]}))
res['robust loss, linear (Huber)']=evaluate(tuned(make_pipeline(StandardScaler(),HuberRegressor(max_iter=2000)),{'huberregressor__alpha':[100,1000,10000]}))
res['robust loss, RBF (SVR C=3)']=evaluate(lambda: make_pipeline(StandardScaler(),SVR(C=3,epsilon=0.1)))
print('--- 3. SVR C curve', flush=True)
for C in [0.1,1,3,10,100]:
    res[f'SVR C={C}']=evaluate(lambda C=C: make_pipeline(StandardScaler(),SVR(C=C,epsilon=0.1)),seeds=(0,))
print('--- 4. k-NN k curve', flush=True)
for k in [1,4,16,64,256]:
    res[f'kNN k={k}']=evaluate(lambda k=k: KNeighborsRegressor(n_neighbors=k,metric='cosine',algorithm='brute',weights='distance'))
print('--- 5. RF spread', flush=True)
res['random forest']=evaluate(lambda: RandomForestRegressor(300,max_features=0.3,min_samples_leaf=3,n_jobs=2,random_state=0),seeds=(0,))
out=pd.DataFrame(res).T
OUT.mkdir(parents=True, exist_ok=True); out.to_csv(OUT / 'diagnostics.csv'); pd.set_option('display.width',220)
print(out.round(3).to_string())
p=PCA().fit(StandardScaler().fit_transform(X)); cv=np.cumsum(p.explained_variance_ratio_)
print('PCA variance explained by 16/64/128/256 comps:', [round(cv[i-1],3) for i in (16,64,128,256)])
print('n train per fold ~', int(len(y)*0.8), 'features 512; MLP params', 512*256+256+257)
print('price range classified', price[chan=='classified'].min(), price[chan=='classified'].max(),
      ' friperie', price[chan=='friperie'].min(), price[chan=='friperie'].max())
r=np.abs(y-np.median(y)); print('share of items with |log dev|>1 (x2.7):', round((r>1).mean(),3))
