//! Placed by the EoH Tunnel Generator (Workbench plugin) at the entrance of every network it builds. Holds the seed and
//! the settings that made it, so the network can be rebuilt exactly or tweaked later. Does nothing in game.
[ComponentEditorProps(category: "EoH/Tunnels", description: "Seed and settings of a tunnel network made by the EoH Tunnel Generator")]
class SP_TunnelGenRecordComponentClass : ScriptComponentClass
{
}

class SP_TunnelGenRecordComponent : ScriptComponent
{
	[Attribute("0", UIWidgets.EditBox, "Layout seed that produced this network")]
	int m_iSeed;

	[Attribute("", UIWidgets.EditBox, "Generator settings (key=value;...)")]
	string m_sSettings;

	[Attribute("", UIWidgets.EditBox, "Hash of the piece catalog used. If it differs from the current catalog, the same seed can give a different network")]
	string m_sCatalogHash;

	[Attribute("0 0 0", UIWidgets.EditBox, "Where the start piece was when the network was generated")]
	vector m_vStartPos;

	[Attribute("0", UIWidgets.EditBox, "Start piece yaw when the network was generated")]
	float m_fStartYaw;

	[Attribute("", UIWidgets.EditBox, "Start piece prefab")]
	ResourceName m_sStartPrefab;

	[Attribute("", UIWidgets.EditBox, "Summary: pieces, length, rooms, entrances")]
	string m_sSummary;
}
