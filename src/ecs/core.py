class World:
    def __init__(self):
        self.next_entity_id = 0
        self.entities = set()
        self.components = {} # component_type -> {entity_id: component_instance}

    def create_entity(self):
        entity = self.next_entity_id
        self.next_entity_id += 1
        self.entities.add(entity)
        return entity

    def add_component(self, entity, component):
        comp_type = type(component)
        if comp_type not in self.components:
            self.components[comp_type] = {}
        self.components[comp_type][entity] = component

    def get_component(self, entity, comp_type):
        if comp_type in self.components:
            return self.components[comp_type].get(entity)
        return None

    def get_entities_with(self, *component_types):
        if not component_types:
            return []
        
        comp_type = component_types[0]
        if comp_type not in self.components:
            return []
        
        valid_entities = set(self.components[comp_type].keys())
        
        for ct in component_types[1:]:
            if ct not in self.components:
                return []
            valid_entities.intersection_update(self.components[ct].keys())
            
        return list(valid_entities)
