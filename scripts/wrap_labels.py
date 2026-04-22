import re
import os

def update_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf8') as f:
        text = f.read()
    
    for k, v in replacements.items():
        text = text.replace(k, v)
        
    with open(filepath, 'w', encoding='utf8') as f:
        f.write(text)

archives_rep = {
    '>Memory Type</label>': '>{t("archives.memory_type", "Memory Type")}</label>',
    '>Agent Attribution</label>': '>{t("archives.agent_attribution", "Agent Attribution")}</label>',
    '>Memory Title</label>': '>{t("archives.memory_title", "Memory Title")}</label>',
    '>Content Payload</label>': '>{t("archives.content_payload", "Content Payload")}</label>',
    '>Decay Class</label>': '>{t("archives.decay_class", "Decay Class")}</label>'
}

update_file('frontend/src/pages/Archives.tsx', archives_rep)

profile_rep = {
    '>Agent Name</label>': '>{t("profile.agent_name", "Agent Name")}</label>',
    '>Active Persona</label>': '>{t("profile.active_persona", "Active Persona")}</label>',
    '>Description</label>': '>{t("profile.description", "Description")}</label>',
    '>Autonomy Level</label>': '>{t("profile.autonomy_level", "Autonomy Level")}</label>',
    '>Select Model</label>': '>{t("profile.select_model", "Select Model")}</label>',
    '>Add Fallback</label>': '>{t("profile.add_fallback", "Add Fallback")}</label>',
    '>Fallback Order</label>': '>{t("profile.fallback_order", "Fallback Order")}</label>',
    '>Routing Strategy</label>': '>{t("profile.routing_strategy", "Routing Strategy")}</label>',
    '>Base Policy</label>': '>{t("profile.base_policy", "Base Policy")}</label>',
    '>Custom Policy Name</label>': '>{t("profile.custom_policy_name", "Custom Policy Name")}</label>',
    '>Job Name</label>': '>{t("profile.job_name", "Job Name")}</label>',
    '>Job Type</label>': '>{t("profile.job_type", "Job Type")}</label>',
    '>Frequency</label>': '>{t("profile.frequency", "Frequency")}</label>',
    '>Priority</label>': '>{t("profile.priority", "Priority")}</label>',
    '>Task Instruction</label>': '>{t("profile.task_instruction", "Task Instruction")}</label>',
    '>Options</label>': '>{t("profile.options", "Options")}</label>'
}

update_file('frontend/src/pages/ShogunProfile.tsx', profile_rep)

torii_rep = {
    '>Policy Name *</label>': '>{t("torii.policy_name", "Policy Name *")}</label>',
    '>Security Tier *</label>': '>{t("torii.security_tier", "Security Tier *")}</label>',
    '>Description</label>': '>{t("torii.description", "Description")}</label>'
}

update_file('frontend/src/pages/Torii.tsx', torii_rep)

print('Updated labels in Archives, ShogunProfile, and Torii.')
