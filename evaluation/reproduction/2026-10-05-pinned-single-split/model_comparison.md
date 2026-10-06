# Customer Churn Model Comparison

| model_name          |   accuracy |   precision |   recall |   roc_auc | confusion_matrix         |
|:--------------------|-----------:|------------:|---------:|----------:|:-------------------------|
| Logistic Regression |   0.799148 |    0.643533 | 0.545455 |  0.849562 | [[922, 113], [170, 204]] |
| Decision Tree       |   0.731725 |    0.494737 | 0.502674 |  0.658343 | [[843, 192], [186, 188]] |
| Random Forest       |   0.789212 |    0.622222 | 0.524064 |  0.833522 | [[916, 119], [178, 196]] |
| XGBoost             |   0.784244 |    0.606707 | 0.532086 |  0.83192  | [[906, 129], [175, 199]] |
| LightGBM            |   0.805536 |    0.658228 | 0.55615  |  0.848423 | [[927, 108], [166, 208]] |

## Selected Model

**Logistic Regression**

### Performance

- Accuracy: 0.7991
- Precision: 0.6435
- Recall: 0.5455
- ROC AUC: 0.8496
- Confusion Matrix: [[922, 113], [170, 204]]

## Why this model was selected

Logistic Regression was selected because it achieved the highest ROC AUC (0.8496), which was the primary model selection criterion. It also demonstrated strong overall performance across accuracy, precision, and recall, making it the best balance of predictive performance among the evaluated models.