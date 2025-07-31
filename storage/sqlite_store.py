def save_resource(session, item: CloudResource):
    existing = session.query(CloudResource).filter_by(
        cloud_account_id=item.cloud_account_id,
        resource_type=item.resource_type,
        resource_id=item.resource_id
    ).first()

    if existing:
        changes = diff_fields(existing, item)
        if changes:
            for field, val in changes.items():
                setattr(existing, field, getattr(item, field))
            existing.fetched_at = item.fetched_at
            session.add(existing)
            print(f"[UPDATED] {item.resource_type} {item.name} with changes: {changes}")
        else:
            print(f"[UNCHANGED] {item.resource_type} {item.name}")
    else:
        session.add(item)
        print(f"[NEW] {item.resource_type} {item.name}")