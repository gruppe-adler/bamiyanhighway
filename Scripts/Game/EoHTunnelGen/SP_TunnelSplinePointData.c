//! What a spline point may ask the EoH Tunnel Generator for (the values of SP_TunnelSplinePointData.m_iKind)
class SP_TunnelSplineKind
{
	static const int ANY = 0;
	static const int STRAIGHT = 1;
	static const int WIDE = 2;			// a straight with "Wide" in its name
	static const int NARROW = 3;		// a straight with "Narrow" in its name
	static const int TURN = 4;
	static const int DOGLEG = 5;
	static const int SLOPE = 6;
	static const int JUNCTION = 7;		// a room with "Junction" in its name (any room if the kit has none)
	static const int ROOM = 8;
	static const int CAP = 9;			// dead end
	static const int ENTRY = 10;

	static string Name(int kind)
	{
		array<string> names = {"any", "straight", "wide straight", "narrow straight", "turn", "dogleg", "slope", "junction", "room", "dead end", "entry"};
		if (kind < 0 || kind >= names.Count())
			return "?";

		return names[kind];
	}
}

//! Per-point settings for the EoH Tunnel Generator's spline (Workbench plugin SP_TunnelGenPlugin). On a SplineShapeEntity
//! or PolylineShapeEntity point: select the point, add this under its Data. The generator puts the asked-for piece where
//! the tunnel reaches the point. Left blank (Any, no prefab): the generator picks as usual. Does nothing in game.
class SP_TunnelSplinePointData : ShapePointDataScriptBase
{
	[Attribute("", UIWidgets.ResourcePickerThumbnail, "This exact piece here: a tunnel piece prefab of the generator's kit (e.g. Prefabs/Tunnels/TT/TT_Room.et). Empty: by the kind below", "et")]
	ResourceName m_sPiece;

	[Attribute("0", UIWidgets.ComboBox, "The kind of piece here, when no exact piece is set", "", { ParamEnum("Any (random, as usual)", "0"), ParamEnum("Straight", "1"), ParamEnum("Wide straight", "2"), ParamEnum("Narrow straight", "3"), ParamEnum("Turn", "4"), ParamEnum("Dogleg", "5"), ParamEnum("Slope", "6"), ParamEnum("Junction", "7"), ParamEnum("Room", "8"), ParamEnum("Dead end", "9"), ParamEnum("Entry", "10") })]
	int m_iKind;

	[Attribute("0", UIWidgets.CheckBox, "No 90 degree turns from this point to the next one (doglegs still break the line of sight)")]
	bool m_bNoTurns;
}
