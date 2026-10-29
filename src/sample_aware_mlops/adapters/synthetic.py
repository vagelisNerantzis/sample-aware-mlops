"""Tiny deterministic stage adapters, not copies of scientific model implementations."""
import math
from .interfaces import StageContext, StageOutput, SampleOutput, StageAdapter
from ..validation.inputs import integer, finite_number, unique_names


def _samples(context: StageContext) -> tuple:
    """Select the exact declared physical cohort before inspecting observation values."""
    indexed={sample.sample_id:sample for sample in context.manifest.samples}
    return tuple(indexed[key] for key in context.sample_ids)


def representation(context: StageContext) -> StageOutput:
    """Project supplied synthetic feature metadata into a declared padded dimension."""
    dimension=integer(context.spec.representation.get('embedding_dim',2),name='embedding dimension',minimum=2)
    if context.spec.fusion.get('method','mean')!='mean':
        raise ValueError('Synthetic adapter supports mean fusion only')
    records=[]
    for sample in _samples(context):
        grouped={}
        for observation in sample.observations:
            values=observation.metadata.get('features',(math.log(9),0.))
            if not isinstance(values,(tuple,list)) or not values:
                raise ValueError('Synthetic features must be a finite numeric vector')
            vector=[finite_number(value,name='synthetic feature') for value in values]
            vector=(vector+[0.]*dimension)[:dimension]
            grouped.setdefault(observation.modality,[]).append(vector)
        if not grouped:
            raise ValueError('Representation needs at least one observation per physical sample')
        embedded={name:[math.fsum(vector[i]/len(vectors) for vector in vectors) for i in range(dimension)]
                  for name,vectors in sorted(grouped.items())}
        records.append(SampleOutput(sample.sample_id,{'embeddings':embedded,
                       'observation_ids':[o.observation_id for o in sample.observations]}))
    return StageOutput('representation',tuple(records))


def acquisition(context: StageContext) -> StageOutput:
    """Select the cheapest single feasible declared view as a toy acquisition action."""
    budget=finite_number(context.spec.acquisition.get('budget',10.),name='synthetic budget',minimum=0)
    if context.spec.acquisition.get('policy','greedy') not in ('greedy','cheapest_feasible'):
        raise ValueError('Synthetic acquisition supports only cheapest-feasible greedy selection')
    samples={sample.sample_id:sample for sample in _samples(context)}
    records=[]
    for record in context.prior_outputs['representation'].records:
        available=record.values['embeddings']
        costs=samples[record.sample_id].acquisition_metadata.get('costs',{})
        values={name:finite_number(costs.get(name,1.),name='synthetic modality cost',minimum=0) for name in available}
        eligible=[name for name in values if values[name]<=budget]
        selected=min(eligible,key=lambda name:(values[name],name)) if eligible else None
        records.append(SampleOutput(record.sample_id,{'selected_modalities':[] if selected is None else [selected],
                       'acquisition_cost':0. if selected is None else values[selected]}))
    return StageOutput('acquisition',tuple(records))


def inference(context: StageContext) -> StageOutput:
    """Compute synthetic softmax scores from selected vectors without reading labels."""
    labels=unique_names(context.spec.evaluation.get('class_labels',('class-a','class-b')),name='class schema')
    if len(labels)<2:
        raise ValueError('Synthetic inference requires at least two declared classes')
    choices={record.sample_id:record.values for record in context.prior_outputs['acquisition'].records} if 'acquisition' in context.prior_outputs else {}
    records=[]
    for record in context.prior_outputs['representation'].records:
        embedded=record.values['embeddings']
        selected=tuple(choices[record.sample_id]['selected_modalities']) if choices else tuple(sorted(embedded))
        if not selected or not set(selected).issubset(embedded):
            raise ValueError('Inference requires at least one feasible known modality')
        dimension=len(next(iter(embedded.values())))
        if dimension<len(labels):
            raise ValueError('Embedding dimension cannot represent the class schema')
        vector=[math.fsum(embedded[m][i]/len(selected) for m in selected) for i in range(dimension)]
        scores=vector[:len(labels)];top=max(scores)
        exponentials=[math.exp(score-top) for score in scores];total=math.fsum(exponentials)
        probabilities=[value/total for value in exponentials]
        records.append(SampleOutput(record.sample_id,{'probabilities':probabilities,
                       'modalities':selected,'acquisition_cost':choices[record.sample_id]['acquisition_cost'] if choices else 0.}))
    return StageOutput('inference',tuple(records))


def evaluation(context: StageContext) -> StageOutput:
    """Compute small cohort accuracy, top-label ECE and failure rate from actual outputs."""
    samples={sample.sample_id:sample for sample in _samples(context)}
    default_labels=tuple(sorted({s.label for s in context.manifest.samples if s.label is not None}))
    labels=unique_names(context.spec.evaluation.get('class_labels',default_labels),name='class schema')
    rows=[];confidences=[];correct=[]
    for record in context.prior_outputs['inference'].records:
        probabilities=record.values['probabilities']
        if len(probabilities)!=len(labels):
            raise ValueError('Prediction dimension differs from declared evaluation classes')
        p=[finite_number(value,name='probability',minimum=0,maximum=1) for value in probabilities]
        if abs(math.fsum(p)-1)>1e-6:
            raise ValueError('Prediction probabilities must sum to one')
        label=samples[record.sample_id].label
        if label is None or label not in labels:
            raise ValueError('Synthetic evaluation needs declared ground truth for every physical sample')
        predicted=max(range(len(p)),key=p.__getitem__)
        success=labels[predicted]==label;confidence=max(p)
        correct.append(success);confidences.append(confidence)
        rows.append(SampleOutput(record.sample_id,{'correct':success,'confidence':confidence,
                     'predicted_label':labels[predicted],'acquisition_cost':record.values['acquisition_cost']}))
    n=len(rows);accuracy=sum(correct)/n
    metrics={'accuracy':accuracy,'failure_rate':1-accuracy}
    if context.spec.evaluation.get('require_calibration',False) or context.spec.evaluation.get('calibration',False):
        ece=0.
        for b in range(10):
            indices=[i for i,c in enumerate(confidences) if b/10<c<=(b+1)/10]
            if indices:
                ece+=len(indices)/n*abs(sum(correct[i] for i in indices)/len(indices)-math.fsum(confidences[i]/len(indices) for i in indices))
        metrics['ece']=ece
    return StageOutput('evaluation',tuple(rows),metrics)


def synthetic_adapters() -> dict[str,StageAdapter]:
    """Return fresh callable bindings; no model training or mutable singleton state."""
    return {'representation':representation,'acquisition':acquisition,'inference':inference,'evaluation':evaluation}
