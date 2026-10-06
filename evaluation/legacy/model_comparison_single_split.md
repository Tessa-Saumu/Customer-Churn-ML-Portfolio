# Customer Churn Model Comparison

| model_name          |   accuracy |   precision |   recall |   roc_auc | confusion_matrix         |
|:--------------------|-----------:|------------:|---------:|----------:|:-------------------------|
| Logistic Regression |   0.801987 |    0.647975 | 0.55615  |  0.849448 | [[922, 113], [166, 208]] |
| Decision Tree       |   0.731725 |    0.494737 | 0.502674 |  0.658343 | [[843, 192], [186, 188]] |
| Random Forest       |   0.789212 |    0.622222 | 0.524064 |  0.833522 | [[916, 119], [178, 196]] |
| XGBoost             |   0.790632 |    0.620061 | 0.545455 |  0.828214 | [[910, 125], [170, 204]] |
| LightGBM            |   0.805536 |    0.658228 | 0.55615  |  0.848423 | [[927, 108], [166, 208]] |

## Selected Model

**Logistic Regression**

### Performance

- Accuracy: 0.8020
- Precision: 0.6480
- Recall: 0.5561
- ROC AUC: 0.8494
- Confusion Matrix: [[922, 113], [166, 208]]

## Why this model was selected

Logistic Regression was selected because it achieved the highest ROC AUC (0.8494), which was the primary model selection criterion. It also demonstrated strong overall performance across accuracy, precision, and recall, making it the best balance of predictive performance among the evaluated models.